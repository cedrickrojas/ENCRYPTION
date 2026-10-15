# IRONVAULT

IRONVAULT is a local-first desktop application for encrypting sensitive text and files. It uses Python and PySide6 for the desktop interface, with no account, server, telemetry, or network service required at runtime.

## Features

- AES-256-GCM authenticated encryption for text and file chunks.
- PBKDF2-HMAC-SHA256 key derivation with 600,000 iterations and a fresh 128-bit salt per operation.
- Fresh random 96-bit nonce for each text envelope and unique counter-derived nonces for file chunks.
- Versioned `.iron` file format with authenticated metadata and streaming I/O.
- Password strength feedback, masked password fields, progress reporting, and safe operation messages.
- Original files are preserved. Partial outputs are removed when an operation fails.
- In-memory activity metadata only: passwords, keys, plaintext, and decrypted content are never logged.

## Installation

From the project folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Windows, if PowerShell blocks activation, run the project with the venv interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

The application is fully offline. It does not require a web server or external service.

## Encryption model

For text, IRONVAULT generates a random salt and nonce, derives a 256-bit key from the password with PBKDF2-HMAC-SHA256, and encrypts the UTF-8 text with AES-256-GCM. The versioned header is authenticated as associated data. The text result is a portable JSON envelope containing only public metadata and ciphertext.

For files, the original is read in 1 MiB chunks. Each chunk is independently authenticated with AES-256-GCM and associated with the authenticated file header and chunk index. This keeps memory use bounded and lets corruption be detected without silently returning damaged content.

Passwords and keys are never written to disk or included in activity records. A strong password is still essential: IRONVAULT cannot recover data when the password is forgotten.

## Supported files

Any regular file can be encrypted. Encrypted files use the `.iron` extension. Decryption accepts `.iron` files and lets you choose the restored output path.

## Test

```powershell
python -m pytest -q
```

The test suite covers text and file round trips, Unicode and special characters, empty inputs, fresh ciphertext, wrong passwords, modified ciphertext, corrupted file data, large streamed content, and preservation of the original file.

## Project structure

```text
IRONVAULT/
├── main.py
├── requirements.txt
├── README.md
├── ironvault/
│   ├── crypto/core.py
│   ├── file_operations/encrypted_file.py
│   ├── services/activity.py
│   └── ui/main_window.py
└── tests/test_crypto.py
```

## Troubleshooting

- `Please enter a password...`: supply a non-empty password.
- `Decryption failed...`: verify the password and ensure the envelope or file was not modified.
- `This file format is not supported.`: choose an IRONVAULT `.iron` file for decryption.
- If the GUI does not open, confirm that the active interpreter has the packages from `requirements.txt` installed.
