# opus_convert

[![Version](https://img.shields.io/badge/version-1.0.1-blue.svg)](https://github.com/pcarbo23/opus_convert)
[![Python](https://img.shields.io/badge/python-3.9+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Spec: ANSI/NISO Z39.86-2002](https://img.shields.io/badge/spec-ANSI%2FNISO_Z39.86--2002-blue.svg)](https://www.daisy.org/z3986/2002/Z3986-2002.html)
[![Spec: NLS Streaming Audiobook (Draft)](https://img.shields.io/badge/spec-NLS_Streaming_Audiobook_(Draft)-orange.svg)](#specifications)

Converts Z39.86 DTBs to the NLS Smart Speaker streaming format.

## Installation & Setup

1. **Clone or navigate to the repository root**:
   ```bash
   cd opus_convert
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies and the package in editable mode**:
   ```bash
   pip install -e .
   ```

## Usage

Once installed in your active virtual environment, you can run the tool using the CLI command `dtb-stream` or as a Python module (`python -m opus_convert.cli`) from anywhere.

```bash
dtb-stream (--master-dir <PATH> | --master-zip <PATH> | --pkg-zip <PATH>) <output_dir> [options]
```

### Input Options (One Required)

*   `--master-dir <PATH>`: Path to a directory containing the DTB files (e.g., a "master" folder). If a subdirectory named `master` exists inside the provided path, it will dive into it automatically.
*   `--master-zip <PATH>`: Path to a ZIP file containing the DTB structure at its root.
*   `--pkg-zip <PATH>`: Path to a 1206:2025 compliant PKG ZIP file.

### Positional Arguments

*   `<output_dir>`: Destination directory for the packaged output zip file.

### Options

*   `-k`, `--keep-temp`: Preserve the intermediate Opus and JSON files in the output directory for debugging.
*   `--amr`: Retain original file extensions (e.g., `.3gp`) found in the XML instead of forcing all audio sources to `.wav`.

---

### Examples

Make sure your virtual environment is active (`source .venv/bin/activate`).

#### Using the `dtb-stream` CLI command (Recommended)

```bash
# Process a 1206:2025 compliant PKG ZIP archive
dtb-stream --pkg-zip /path/to/db135170.pkg.zip ~/nlsbpd -k

# Process a local uncompressed master DTB directory
dtb-stream --master-dir ./my_dtb_book ./output_dir

# Process a master ZIP archive
dtb-stream --master-zip ./my_dtb_book.zip ./output_dir
```

#### Running as a Python module

Always run module commands from the **project root directory** (do not `cd` into `src` or `src/opus_convert`):

```bash
python -m opus_convert.cli --pkg-zip /path/to/db135170.pkg.zip ~/nlsbpd -k
```

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'opus_convert'`**:
  - Ensure your virtual environment is active (`source .venv/bin/activate`).
  - Run the command from the project root directory rather than inside `src/` or `src/opus_convert/`.
  - Ensure the package has been installed with `pip install -e .`.
  - When using the `-m` flag, pass the module path `opus_convert.cli` without the `.py` extension (e.g., `python -m opus_convert.cli ...`).

---

## Specifications

*   **Z39 DTB Specification**: [ANSI/NISO Z39.86-2002](https://www.daisy.org/z3986/2002/Z3986-2002.html) - Specifications for the Digital Talking Book.
*   **NLS Streaming Audiobook Specification**: National Library Service (NLS) Smart Speaker Streaming Audiobook specification (*Draft*).

---

## AMR-WB+ Decoder Notice

> [!IMPORTANT]
> The AMR-WB+ codec is patent-protected, and its distribution is controlled by the National Library Service (NLS). Authorized users must contact the NLS PICS Admin in order to acquire the codec.



