"""
Fernet-based file encryption with zlib compression for secure storage.
Compresses before encrypting, decompresses after decrypting.
Backward-compatible with legacy uncompressed files.
"""
import os
import uuid
import zlib
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_fernet = None

# Magic header to identify compressed files
_COMPRESS_HEADER = b'CMP1'


def _get_fernet():
    """Get or initialize the Fernet cipher."""
    global _fernet
    if _fernet is None:
        key = os.getenv('FERNET_KEY', '')
        if not key or key == 'placeholder-will-be-generated-on-first-run':
            key = Fernet.generate_key().decode()
            logger.warning(f"Generated new Fernet key. Add to .env: FERNET_KEY={key}")
            _save_fernet_key(key)
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def _save_fernet_key(key):
    """Save generated Fernet key to .env file."""
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                content = f.read()
            content = content.replace(
                'FERNET_KEY=placeholder-will-be-generated-on-first-run',
                f'FERNET_KEY={key}'
            )
            with open(env_path, 'w') as f:
                f.write(content)
            logger.info("Fernet key saved to .env")
    except Exception as e:
        logger.error(f"Failed to save Fernet key: {e}")


def get_storage_path(user_id, filename=None, subdir='resumes'):
    """Get the encrypted file storage path for a user."""
    base_path = os.getenv('STORAGE_PATH',
                          os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'storage'))

    user_dir = os.path.join(base_path, 'users', str(user_id), subdir)
    os.makedirs(user_dir, exist_ok=True)

    if filename is None:
        filename = f"{uuid.uuid4()}.enc"
    elif not filename.endswith('.enc'):
        filename = f"{os.path.splitext(filename)[0]}_{uuid.uuid4().hex[:8]}.enc"

    return os.path.join(user_dir, filename)


def get_avatar_path(user_id):
    """Get the encrypted avatar storage path for a user."""
    return get_storage_path(user_id, subdir='avatar')


def encrypt_and_save(data, file_path):
    """Compress, encrypt and save data to file.

    Args:
        data: bytes to compress & encrypt
        file_path: path to save encrypted file

    Returns:
        file_path on success
    """
    try:
        f = _get_fernet()
        raw = data if isinstance(data, bytes) else data.encode()

        # Compress then prepend header
        compressed = _COMPRESS_HEADER + zlib.compress(raw, level=6)
        encrypted = f.encrypt(compressed)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as fp:
            fp.write(encrypted)

        original_size = len(raw)
        stored_size = len(encrypted)
        ratio = (1 - stored_size / max(original_size, 1)) * 100
        logger.info(f"File compressed & encrypted: {file_path} "
                     f"(original={original_size}B, stored={stored_size}B, ratio={ratio:.1f}%)")
        return file_path
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_and_read(file_path):
    """Decrypt and decompress file contents in-memory.

    Backward-compatible: detects whether data was compressed.

    Args:
        file_path: path to encrypted file

    Returns:
        decrypted (and decompressed) bytes
    """
    try:
        f = _get_fernet()
        with open(file_path, 'rb') as fp:
            encrypted = fp.read()
        decrypted = f.decrypt(encrypted)

        # Check for compression header
        if decrypted[:4] == _COMPRESS_HEADER:
            decrypted = zlib.decompress(decrypted[4:])

        logger.info(f"File decrypted: {file_path}")
        return decrypted
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


def delete_encrypted(file_path):
    """Securely delete an encrypted file."""
    try:
        if os.path.exists(file_path):
            # Overwrite with random data before deleting
            file_size = os.path.getsize(file_path)
            with open(file_path, 'wb') as fp:
                fp.write(os.urandom(file_size))
            os.remove(file_path)
            logger.info(f"File securely deleted: {file_path}")
    except Exception as e:
        logger.error(f"Secure delete failed: {e}")
