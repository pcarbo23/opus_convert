import json
import datetime
import zipfile
import tempfile
import ffmpeg
from typing import Any
from pathlib import Path
from opus_convert.parser import DTBParser
from opus_convert.audio import AudioEncoder
from . import __version__

tool_name = "Opus Convert"

class StreamingConverter:
    def __init__(self, input_path: Path, output_dir: Path, input_mode: str = "master-dir", keep_temp: bool = False, amr: bool = False):
        self.input_path = input_path
        self.output_dir = output_dir
        self.input_mode = input_mode
        self.keep_temp = keep_temp
        self.amr = amr
        self._temp_dir_obj = None

    def _get_wav_duration(self, wav_path: Path) -> float:
        """Determines the exact duration of a WAV file using ffprobe."""
        try:
            probe = ffmpeg.probe(str(wav_path))
            return float(probe['format']['duration'])
        except (ffmpeg.Error, KeyError, ValueError) as e:
            print(f"Error probing {wav_path}: {e}")
            return 0.0

    def _format_etime(self, seconds: float) -> str:
        """Formats seconds into h:MM:SS.mmm string strictly."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        
        # Handle millisecond overflow
        if millis >= 1000:
            secs += millis // 1000
            millis = millis % 1000
        if secs >= 60:
            minutes += secs // 60
            secs = secs % 60
        if minutes >= 60:
            hours += minutes // 60
            minutes = minutes % 60
            
        return f"{hours}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def _calculate_master_times(self, nav_nodes, wav_offsets):
        """Recursively recalculates master timestamps for navigation nodes."""
        processed = []
        for node in nav_nodes:
            wav_name = node['wav']
            # Only process if we have a valid WAV offset
            if wav_name in wav_offsets:
                master_timestamp = wav_offsets[wav_name] + node['clipBegin']
                
                final_node = {
                    "label": node['label'],
                    "etime": self._format_etime(master_timestamp)
                }
                
                # Recursively process children
                children = node.get('navPoints', [])
                if children:
                    final_node["navPoints"] = self._calculate_master_times(
                        children, wav_offsets
                    )
                    
                processed.append(final_node)
        return processed

    def _prepare_working_directory(self, input_path: Path, mode: str) -> Path:
        """Prepares a flat working directory from various input formats."""
        if mode == "master-dir":
            return input_path

        # For ZIP modes, create a temporary directory
        self._temp_dir_obj = tempfile.TemporaryDirectory()
        working_dir = Path(self._temp_dir_obj.name)

        if mode == "master-zip":
            print(f"Extracting master ZIP: {input_path}")
            with zipfile.ZipFile(input_path, 'r') as zf:
                zf.extractall(working_dir)
            return working_dir

        if mode == "pkg-zip":
            print(f"Extracting PKG ZIP: {input_path}")
            with zipfile.ZipFile(input_path, 'r') as zf:
                zf.extractall(working_dir)
            
            # Locate internal .dtb.zip dynamically
            dtb_zips = list(working_dir.glob("*.dtb.zip"))
            if not dtb_zips:
                raise FileNotFoundError("Could not find internal .dtb.zip in PKG structure.")
            
            # Extensions to extract from the dtb.zip
            valid_extensions = ['.opf', '.ncx', '.smil']
            if self.amr:
                valid_extensions.append('.3gp')

            with zipfile.ZipFile(dtb_zips[0], 'r') as zf:
                for member in zf.namelist():
                    # Merge required files into the flat working directory
                    if any(member.lower().endswith(ext) for ext in valid_extensions):
                        zf.extract(member, working_dir)

            return working_dir

        return input_path

    def process(self):
        utc_now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # 0. Prepare flat workspace from potentially compressed inputs
        working_dir = self._prepare_working_directory(self.input_path, self.input_mode)
        
        try:
            parser = DTBParser(working_dir, use_amr=self.amr)
            opus_dir = self.output_dir / "opus"
            opus_dir.mkdir(parents=True, exist_ok=True)

            # 1. Parse Metadata
            metadata = parser.extract_metadata()
            # Ensure we look for dc:Identifier
            uid = metadata.get('dc:Identifier')
            if isinstance(uid, list):
                uid = uid[0]
            if not uid:
                uid = "unknown_book"
            uid = "".join(c for c in uid if c.isalnum() or c in ('-', '_')).strip()

            # 2. Extract Audio Sequence
            sequence = parser.extract_audio_sequence()
            wav_files = sequence['wav_files']
            raw_navigation = sequence['navigation']

            # 3. Calculate Master Timeline Offsets
            wav_offsets = {}
            running_total_duration = 0.0
            
            for wav_path in wav_files:
                wav_offsets[wav_path.name] = running_total_duration
                duration = self._get_wav_duration(wav_path)
                running_total_duration += duration

            # 4. Recalculate Navigation Timestamps (Recursive)
            navigation = self._calculate_master_times(raw_navigation, wav_offsets)

            # 5. Encode Audio
            audio_filename = f"{uid}.opus"
            audio_out_path = opus_dir / audio_filename
            encoder = AudioEncoder(audio_out_path)
            encoder.concatenate_and_encode(wav_files)

            # 6. Generate JSON Document
            json_filename = f"{uid}.json"
            json_out_path = opus_dir / json_filename
            
            # Initializing output_data as a new dictionary with @context as the FIRST key
            output_data: dict[str, Any] ={
                "@context": {
                    "dc": "http://purl.org/dc/elements/1.1/",
                    "dtb": "http://www.daisy.org/z3986/2005/dtb/",
                    "nls": "http://www.loc.gov/nls/metadata/",
                    "dcterms": "http://purl.org/dc/terms/"
                }
            }
            
            # Merge metadata into the dictionary
            output_data.update(metadata)
            
            # Apply metadata overrides and additions (with dc: prefixes)
            output_data.update({"dcterms:modified": utc_now})
            output_data.update({"dc:Type": [
                'Sound',
                'InteractiveResource'
            ]})
            output_data.update({"nls:generator": f"{tool_name} v{__version__}"})
            output_data["dc:Date"] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
            output_data["dc:Publisher"] = "National Library Service for the Blind and Print Disabled, Library of Congress"
            output_data["dc:Format"] = [
                "application/audiobook+zip", 
                "audio/opus", 
                "application/ld+json",
                "NLS Streaming Audiobook"
            ]
            # goats = 'get the total audio duration from the final opus file derived from the concatenated WAVs'
            # output_data["dtb:totalTime"] = goats

            # Navigation array attached LAST
            output_data["navPoints"] = navigation

            with open(json_out_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4)

            # 7. Package Deliverable
            # Strip the "us-nls-"  from the uid to create the proper zip filename
            clean_uid = uid.replace("us-nls-", "")
            zip_filename = f"{clean_uid}.streaming.zip"
            zip_out_path = self.output_dir / zip_filename

            with zipfile.ZipFile(zip_out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(json_out_path, arcname=json_filename)
                if audio_out_path.exists():
                    zf.write(audio_out_path, arcname=audio_filename)

            # 8. Cleanup routine
            if not self.keep_temp:
                print(f"Cleaning up intermediate files in {opus_dir}...")
                json_out_path.unlink(missing_ok=True)
                audio_out_path.unlink(missing_ok=True)
                try:
                    opus_dir.rmdir()
                except OSError:
                    pass # Directory not empty or other issue
            else:
                print(f"Preserving intermediate files in {opus_dir}.")

            print(f"Packaged streaming audiobook into {zip_out_path}")
            return zip_out_path

        finally:
            # Cleanup temporary working directory if one was created
            if self._temp_dir_obj:
                print("Cleaning up temporary workspace...")
                self._temp_dir_obj.cleanup()
