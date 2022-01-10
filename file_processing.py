import hashlib
import shutil
import traceback
import zipfile


def trim_file(file, removed_bytes_number, save_bytes=False):
    """ Remove x bytes from the file and (OPTIONAL) get the missing bytes

    :param file: The file that will be modified
    :param removed_bytes_number: The number of bytes that will be removed
    :param save_bytes: If True function will also return the bytes deleted (default False)
    :return: The name of the file if save_bytes was set to False.
        If save_bytes is set to yes the bytes deleted will also be returned
    """
    while True:
        try:
            f = open(file, 'r+b')
            f_size = f.seek(0, 2)
            f.seek(f_size - removed_bytes_number, 0)
            if save_bytes:
                removed = f.read(removed_bytes_number)
                f.seek(f_size - removed_bytes_number, 0)
            f.truncate()
            f.close()
        except Exception as e:
            print("An error occured in trim_file")
            print(e)
            continue
        if save_bytes:
            return file, removed
        return file


def trim_archive(archive, removed_bytes_number, copy=False, c_name='truncated_archive', save_bits=False):
    """Get the name of the trimmed archive or get a modified copy.

    :param archive: The name of the initial archive
    :param removed_bytes_number: The number of bytes that will be removed
    :param copy: If True function will return a copy of the archive and not modify the one sent (default False)
    :param c_name: The name of the archive copy (default truncated_archive)
    :param save_bits: If True function will also return the bytes deleted (default False)
    :return: The name of the file if save_bytes was set to False.
        If save_bytes is set to yes the bytes deleted will also be returned
    """
    if copy:
        copy_name = f"{c_name}.{archive.split('.')[-1]}"
        shutil.copyfile(archive, copy_name)  # create a copy of the archive
        if save_bits:
            return trim_file(copy_name, removed_bytes_number, save_bits)
        return trim_file(copy_name, removed_bytes_number)
    return trim_file(archive, removed_bytes_number)


def compute_hash_unopened_file(file, hash_type):
    """Compute the hash of a file that is not already opened

    :param file: The file that will be used
    :param hash_type: The hash method (any hashlib method sent as a string e.g. 'md5')
    :return: The hash of the file as a string
    """
    with open(file, 'rb') as f:
        return compute_hash_opened_file(f, hash_type)


def compute_hash_opened_file(file, hash_type):
    """Compute the hash of a file that was previously opened

    :param file: A file object
    :param hash_type: The hash method (any hashlib method sent as a string e.g. 'md5')
    :return:
    """
    m = hashlib.new(hash_type)
    while chunk := file.read(1024):
        m.update(chunk)
    return m.hexdigest()


def append_bytes_to_file(file, bytes_to_append):
    """Appends the bytes sequence to the end of the file

    :param file: The file that will be modified
    :param bytes_to_append: The byte string that will be added to the file
    :return: The length of the byte string appended
    """
    f = open(file, 'ab')
    f.write(bytes_to_append)
    f.close()
    return len(bytes_to_append)


def check_archive_validity(archive, bytes_to_add, file_name, file_hash, hash_method):
    """Verifies if adding the bytes_to_add byte string to the end of the archive returns
    a valid archive and if the file given can be extracted from the archive.

    :param archive: The name of the archive which will be modified
    :param bytes_to_add: The byte string that will be appended to the end of the archive
    :param file_name: The name of the file to be extracted from the archive
    :param file_hash: The hash of the initial file
    :param hash_method: The method of generating the file_hash (any hashlib method sent as a string e.g. 'md5')
    :return: True if file_name can be extracted from the archive (THE ARCHIVE WON'T BE MODIFIED)
    """
    added_bytes_length = append_bytes_to_file(archive, bytes_to_add)
    try:
        z = zipfile.ZipFile(archive)
        f = z.open(file_name)
        computed_hash = compute_hash_opened_file(f, hash_method)
        if computed_hash == file_hash:
            return True
        return False
    except Exception as e:
        # TODO check other exception type
        # BadZipFile when the archive is corrupted
        # Errno 22 when the archive is valid but the file inside is corrupted
        if type(e).__name__ == 'BadZipFile' or '[Errno 22]' in str(e):
            pass
        else:
            print("@@@@ NEW ERROR FOUND @@@@")
            print(e)
            print(archive)
            traceback.print_exc()
            exit()
    finally:
        trim_archive(archive, added_bytes_length)