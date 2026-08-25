from lxml import etree
from pathlib import Path
import re
from collections import defaultdict
import langcodes


class DTBParser:
    def __init__(self, dtb_dir: Path, use_amr: bool = False):
        self.dtb_dir = dtb_dir
        self.use_amr = use_amr
        self.opf_file = self._find_opf()

    def _find_opf(self):
        # Implementation to locate the .opf file in the directory
        opfs = list(self.dtb_dir.glob("*.opf"))
        if not opfs:
            raise FileNotFoundError("No OPF file found in the target directory.")
        return opfs[0]

    def _normalize_language(self, tag: str) -> str:
        """
        Normalizes a language tag to RFC 5646 standard using langcodes.
        Simplifies to base language if it's the default for the region.
        """
        if not tag:
            return "en"
        try:
            # Standardize the tag
            standardized = langcodes.standardize_tag(tag)
            # Simplify if it's a default region (e.g., en-US -> en)
            simplified = langcodes.Language.get(standardized).simplify().to_tag()
            return simplified
        except Exception:
            # Return raw tag if standardization fails but it's not empty
            return tag.strip() if tag.strip() else "en"

    def _parse_npt(self, npt_str: str) -> float:
        """
        Converts npt= time string formats into float seconds.
        Supported formats: npt=12.345s, npt=0:01:23.45, etc.
        """
        if not npt_str:
            return 0.0

        # Remove 'npt=' prefix if present
        time_val = npt_str.replace("npt=", "").strip()

        # Format: 12.345s
        if time_val.endswith('s'):
            try:
                return float(time_val[:-1])
            except ValueError:
                return 0.0

        # Format: HH:MM:SS.ms or MM:SS.ms
        parts = time_val.split(':')
        try:
            if len(parts) == 3:  # HH:MM:SS.ms
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:  # MM:SS.ms
                return int(parts[0]) * 60 + float(parts[1])
            else:
                return float(time_val)
        except ValueError:
            return 0.0

    def extract_metadata(self) -> dict:
        """
        Extracts OPF metadata into the required JSON root object name/value pairs.
        Selectively filters for core Dublin Core and specific Extended metadata.
        """
        tree = etree.parse(str(self.opf_file))

        # Core Dublin Core fields to retain
        dc_fields = {
            'Title', 'Creator', 'Description', 'Publisher',
            'Format', 'Language', 'Rights', 'Identifier'
        }
        
        # Specific Extended Metadata fields to retain
        x_meta_fields = {
            'dtb:sourceRights', 'dtb:totalTime', 'dtb:narrator', 'dtb:producer', 'nls:recordingAgency'
        }

        raw_metadata = defaultdict(list)
        # Updated forced arrays to match retained dc: keys
        forced_arrays = {'dc:Creator', 'dtb:narrator'}

        # Locate the metadata block
        metadata_blocks = tree.xpath("//*[local-name()='metadata']")
        if not metadata_blocks:
            return {}

        # Iterate through all descendants of the metadata block
        for elem in metadata_blocks[0].iterdescendants():
            localname = etree.QName(elem).localname

            # Dublin Core Metadata - prepend dc: prefix
            if localname in dc_fields:
                if elem.text and elem.text.strip():
                    key = f"dc:{localname}"
                    value = elem.text.strip()
                    
                    # Normalize Language field
                    if localname == 'Language':
                        value = self._normalize_language(value)
                        
                    raw_metadata[key].append(value)

            # Selective Extended Metadata
            elif localname == 'meta':
                name = elem.get('name')
                content = elem.get('content')
                if name in x_meta_fields and content:
                    raw_metadata[name].append(content.strip())

        # Final formatting according to NLS rules
        metadata = {}
        for key, values in raw_metadata.items():
            if key in forced_arrays:
                metadata[key] = values
            else:
                metadata[key] = values[0] if len(values) == 1 else values

        # Ensure forced arrays exist even if empty
        for key in forced_arrays:
            if key not in metadata:
                metadata[key] = []

        return metadata

    def _process_nav_point(self, nav_point, smil_lookup):
        """Recursive helper to extract navPoint data while preserving nesting."""
        nav_class = nav_point.get('class')

        label_elem = nav_point.xpath(".//*[local-name()='navLabel']/*[local-name()='text']")
        label_text = label_elem[0].text if label_elem else ""
        clean_label = " ".join(label_text.split()) if label_text else ""

        content_elem = nav_point.xpath(".//*[local-name()='content']")
        raw_src = content_elem[0].get('src') if content_elem else None

        lookup_key = None
        if raw_src:
            parts = raw_src.split('#')
            file_part = parts[0].split('/')[-1] if parts[0] else ""  # Get filename only
            id_part = parts[1] if len(parts) > 1 else ""
            lookup_key = f"{file_part}#{id_part}"

        lookup = smil_lookup.get(lookup_key, {'wav': None, 'clipBegin': 0.0})

        if lookup['wav'] is None:
            print(
                f"DEBUG: SMIL lookup failed for NCX src: {raw_src} (normalized to {lookup_key}). This navPoint will have no audio reference.")

        node = {
            "class": nav_class,
            "label": clean_label,
            "wav": lookup['wav'],
            "clipBegin": lookup['clipBegin']
        }

        children = nav_point.xpath("./*[local-name()='navPoint']")
        if children:
            node["navPoints"] = [self._process_nav_point(child, smil_lookup) for child in children]

        return node

    def extract_audio_sequence(self):
        """
        Parses SMIL files for WAV sequence and uses NCX for structured navigation.
        """
        tree = etree.parse(str(self.opf_file))
        ns = {'opf': tree.getroot().nsmap.get(None, 'http://openebook.org/namespaces/oebpkg/1.0/')}

        # 1. Build Manifest Map (still needed for smil_files list)
        manifest = {}
        for item in tree.xpath("//opf:manifest/opf:item", namespaces=ns):
            manifest[item.get('id')] = item.get('href')

        # 2. Get Spine Order
        spine_items = tree.xpath("//opf:spine/opf:itemref", namespaces=ns)
        smil_files = [manifest.get(item.get('idref')) for item in spine_items]
        smil_files = [f for f in smil_files if f and f.endswith('.smil')]

        # 3. PASS 1: Build SMIL Lookup & WAV Sequence
        wav_sequence = []
        seen_wavs = set()
        smil_lookup = {}

        for smil_name in smil_files:
            smil_path = self.dtb_dir / smil_name
            if not smil_path.exists():
                continue

            smil_tree = etree.parse(str(smil_path))
            for par in smil_tree.xpath("//*[local-name()='par']"):
                audio = par.xpath(".//*[local-name()='audio']")
                if not audio:
                    continue

                audio_tag = audio[0]
                src = audio_tag.get('src')
                if not src:
                    continue

                raw_file = src.split('#')[0] if '#' in src else src
                
                # Enforce .wav unless AMR is explicitly allowed
                if self.use_amr:
                    wav_file = raw_file
                else:
                    wav_file = str(Path(raw_file).with_suffix('.wav'))

                if wav_file not in seen_wavs:
                    wav_sequence.append(wav_file)
                    seen_wavs.add(wav_file)

                par_id = par.get('id')
                # Normalize SMIL lookup key: filename#id
                smil_ref = f"{smil_path.name}#{par_id}"
                smil_lookup[smil_ref] = {
                    'wav': wav_file,
                    'clipBegin': self._parse_npt(audio_tag.get('clipBegin'))
                }

        # 4. PASS 2: Parse NCX Recursively
        navigation = []
        # Dynamic NCX Discovery
        ncx_files = list(self.dtb_dir.glob("*.ncx"))
        ncx_path = ncx_files[0] if ncx_files else None

        if ncx_path and ncx_path.exists():
            ncx_tree = etree.parse(str(ncx_path))
            nav_map = ncx_tree.xpath("//*[local-name()='navMap']")
            if nav_map:
                root_points = nav_map[0].xpath("./*[local-name()='navPoint']")
                navigation = [self._process_nav_point(p, smil_lookup) for p in root_points]
        else:
            print(f"WARNING: No NCX file found in {self.dtb_dir}. Navigation will be empty.")

        return {
            'wav_files': [self.dtb_dir / w for w in wav_sequence],
            'navigation': navigation
        }
