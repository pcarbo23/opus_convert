import ffmpeg
import os
import sys
import time
import threading
import itertools
import hashlib
import wave
import ctypes
import tempfile
import platform
import subprocess
from pathlib import Path


class AudioEncoder:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self._spinner_running = threading.Event()
        self.os_type = platform.system()
        self.bridge = None
        self.linux_binary = None

    def _prepare_decoder(self):
        if self.os_type == 'Darwin':
            if self.bridge is None:
                lib_path = Path(__file__).parent.absolute() / "libamr_bridge.dylib"
                try:
                    self.bridge = ctypes.CDLL(str(lib_path))
                    self.bridge.convert_3gp_to_wav.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    self.bridge.convert_3gp_to_wav.restype = ctypes.c_int
                except Exception as e:
                    raise RuntimeError(f"Failed to load AMR-WB+ decoder library: {e}")
        elif self.os_type == 'Linux':
            if self.linux_binary is None:
                binary_path = Path(__file__).parent.absolute() / "amr-dec"
                if not binary_path.exists():
                    raise RuntimeError(f"AMR-WB+ decoder binary not found at {binary_path}")
                self.linux_binary = binary_path
        elif self.os_type == 'Windows':
            raise NotImplementedError("AMR-WB+ decoding is not currently supported on Windows.")
        else:
            raise NotImplementedError(f"AMR-WB+ decoding is not supported on platform: {self.os_type}")

    def _decode_amr_to_wav(self, file_path: Path) -> Path:
        if file_path.suffix.lower() != '.3gp':
            return file_path
        
        self._prepare_decoder()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            
        try:
            if self.os_type == 'Darwin':
                result = self.bridge.convert_3gp_to_wav(
                    str(file_path).encode('utf-8'),
                    str(temp_path).encode('utf-8')
                )
                if result != 0:
                    raise RuntimeError(f"AMR decoding failed with code {result}")
            elif self.os_type == 'Linux':
                subprocess.run(
                    [str(self.linux_binary), '-fs', '41000', '-if', str(file_path), '-of', str(temp_path)],
                    check=True,
                    capture_output=True
                )
        except Exception as e:
            if temp_path.exists():
                os.remove(temp_path)
            raise RuntimeError(f"AMR decoding failed: {e}")
            
        return temp_path

    def _play_spinner(self, message="Encoding audio... "):
        """Simple CLI spinner animation."""
        spinner = itertools.cycle(['|', '/', '-', '\\'])
        while self._spinner_running.is_set():
            sys.stdout.write(f"\r{message}{next(spinner)}")
            sys.stdout.flush()
            time.sleep(0.1)
        # Clear the spinner line
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()

    def _calculate_pcm_md5(self, wav_files: list[Path]) -> str:
        """Calculates MD5 hash of raw PCM data from multiple WAV files."""
        md5 = hashlib.md5()
        chunk_size = 65536  # 64KB
        
        for wav_path in wav_files:
            try:
                with wave.open(str(wav_path), 'rb') as wf:
                    while True:
                        data = wf.readframes(chunk_size // (wf.getsampwidth() * wf.getnchannels()))
                        if not data:
                            break
                        md5.update(data)
            except wave.Error as e:
                print(f"Warning: Could not read PCM data from {wav_path}: {e}")
        
        return md5.hexdigest()

    def concatenate_and_encode(self, input_files: list[Path]):
        """
        Concatenates and encodes input files (decoding AMR-WB+ files if needed) using FFmpeg concat demuxer.
        Includes a silent execution with error handling and a progress spinner.
        Calculates and embeds an MD5 hash of the raw PCM data.
        """
        processed_wavs = []
        temp_files_to_cleanup = []

        try:
            # Pre-process inputs: transcode AMR-WB+ (.3gp) files to WAV if needed
            for file_path in input_files:
                decoded_path = self._decode_amr_to_wav(file_path)
                processed_wavs.append(decoded_path)
                if decoded_path != file_path:
                    temp_files_to_cleanup.append(decoded_path)

            # 1. Calculate PCM Hash
            print("Calculating PCM integrity hash...")
            pcm_hash = self._calculate_pcm_md5(processed_wavs)
            print(f"Integrity hash generated: {pcm_hash}")

            concat_list_path = self.output_path.parent / "concat_list.txt"
            
            try:
                # 2. Prepare concat list
                with open(concat_list_path, 'w', encoding='utf-8') as f:
                    for wav in processed_wavs:
                        safe_path = str(wav.absolute()).replace("'", "'\\''")
                        f.write(f"file '{safe_path}'\n")

                # 3. Build FFmpeg command with metadata injection
                input_node = ffmpeg.input(str(concat_list_path), format='concat', safe=0)
                output = ffmpeg.output(
                    input_node,
                    str(self.output_path),
                    acodec='libopus',
                    ac=1,
                    ar=48000,
                    vn=None,
                    metadata=f"md5sum={pcm_hash}",
                    **{
                        'b:a': '24k',
                        'vbr': 'on',
                        'compression_level': 10,
                        'application': 'voip',
                        'frame_duration': 20
                    }
                )

                # 4. Start spinner thread
                self._spinner_running.set()
                spinner_thread = threading.Thread(target=self._play_spinner)
                spinner_thread.start()

                # 5. Run FFmpeg silently
                try:
                    output.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
                    print("Audio encoding complete! Metadata embedded.")
                except ffmpeg.Error as e:
                    print(f"\nFFmpeg Error Output:\n{e.stderr.decode()}")
                    raise e
                finally:
                    # 6. Stop spinner
                    self._spinner_running.clear()
                    spinner_thread.join()

            finally:
                # 7. Cleanup temporary list file
                if concat_list_path.exists():
                    os.remove(concat_list_path)

        finally:
            # 8. Cleanup temporary WAV files
            for temp_path in temp_files_to_cleanup:
                temp_path.unlink(missing_ok=True)
