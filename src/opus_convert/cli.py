import argparse
import sys
from pathlib import Path
from opus_convert.converter import StreamingConverter

# TODO why when I try to run this in the terminal I get an error?

def main():
    parser = argparse.ArgumentParser(description="Convert Z39.86 DTB to Streaming Audiobook Format.")
    
    # Mutually exclusive group for input sources
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--master-dir", type=Path,
                        help="Path to a directory containing the DTB files (e.g., a 'master' folder).")
    group.add_argument("--master-zip", type=Path,
                        help="Path to a ZIP file containing the DTB structure at the root.")
    group.add_argument("--pkg-zip", type=Path,
                        help="Path to a 1206:2025 compliant PKG ZIP file.")

    parser.add_argument("output_dir", type=Path, help="Destination for the packaged zip file.")
    parser.add_argument("-k", "--keep-temp", action="store_true",
                        help="Preserve the intermediate Opus and JSON files for debugging.")
    parser.add_argument("--amr", action="store_true",
                        help="If set, retain original file extensions (e.g., .3gp) found in XML. Defaults to forcing all audio sources to .wav")

    args = parser.parse_args()

    # Determine input path and mode
    input_path = None
    input_mode = None

    if args.master_dir:
        input_path = args.master_dir
        input_mode = "master-dir"
    elif args.master_zip:
        input_path = args.master_zip
        input_mode = "master-zip"
    elif args.pkg_zip:
        input_path = args.pkg_zip
        input_mode = "pkg-zip"

    # Directory dive logic for master-dir
    if input_mode == "master-dir":
        nodrm_path = input_path / "master"
        if nodrm_path.exists() and nodrm_path.is_dir():
            input_path = nodrm_path

    if not input_path.exists():
        print(f"Error: Input {input_path} does not exist.")
        sys.exit(1)

    # Instantiate converter with mode and path
    converter = StreamingConverter(
        input_path, 
        args.output_dir, 
        input_mode=input_mode, 
        keep_temp=args.keep_temp,
        amr=args.amr
    )
    
    try:
        converter.process()
        print("Conversion completed successfully.")
    except Exception as e:
        print(f"Failed to process DTB: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
