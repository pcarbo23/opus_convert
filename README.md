# opus_convert

Converts Z39.86 DTBs to the NLS Smart Speaker streaming format.

## Installation

```bash
pip install -e .
```

## Usage

```bash
dtb-stream (--master-dir <PATH> | --master-zip <PATH> | --pkg-zip <PATH>) <output_dir> [options]
```

### Input Options (One Required)

*   `--master-dir <path>`: Path to a directory containing the DTB files (e.g., a "master" folder). If a subdirectory named `master` exists inside the provided path, it will dive into it automatically.
*   `--master-zip <path>`: Path to a ZIP file containing the DTB structure at its root.
*   `--pkg-zip <path>`: Path to a 1206:2025 compliant PKG ZIP file.

### Arguments

*   `output_dir`: Destination directory for the packaged zip file.

### Options

*   `-k`, `--keep-temp`: Preserve the intermediate Opus and JSON files in the output directory for debugging.
*   `--amr`: Retain original file extensions (e.g., `.3gp`) found in the XML instead of forcing all audio sources to `.wav`.

### Examples

```bash
# Process a local uncompressed master DTB directory
dtb-stream --master-dir ./my_dtb_book ./output_dir

# Process a master ZIP archive
dtb-stream --master-zip ./my_dtb_book.zip ./output_dir

# Process a 1206:2025 compliant PKG ZIP archive
dtb-stream --pkg-zip ./my_pkg_book.zip ./output_dir

# Alternatively, run directly as a module during development:
python -m opus_convert.cli --master-dir ./my_dtb_book ./output_dir
```

## AMR-WB+ Decoder Notice

> [!IMPORTANT]
> The AMR-WB+ codec is patent-protected, and its distribution is controlled by the National Library Service (NLS). Authorized users must contact the NLS PICS Admin in order to acquire the codec.


