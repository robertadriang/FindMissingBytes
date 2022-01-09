# Sa se scrie un tool care primeste un hash pentru un fisier originial si o arhiva trunchiata
# (maxim “x” bytes de la finalul arhivei originale lipsesc).
# Tool-ul va gasi fisierul original din arhiva
# ( in momentul in care se va despacheta fisierul din arhiva va avea acelasi hash ca cel primit la input )
# Pentru rezolvarea acestei probleme este imperativa folosirea oricarei forme de paralelizare (
#
# multi threding/multiuprocessing / multi system / etc )
# INPUT:
# Arhiva truncata
# Numele fisierului din arhiva
# Hash-ul expected al fisierului
# Optional ar fi utila si o optiune de trunchiere a unei arhive si generare a datelor de input de
# mai sus.
# OUTPUT:
# Continutul fisierului dupa ce a fost dezarhivat cu success
import hashlib
import os
import shutil
import zipfile
from multiprocessing import Process, Queue, Lock, Pipe
from queue import Empty
import traceback


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


def initialize_generator_power(start_number):
    """Set the start upper limit of the generator

    :param start_number: The start value of the generator
    :return: The lowest power bigger than the number given
    """
    power = 1
    while 256 ** power <= start_number:
        power += 1
    return power


def byte_generator(start, stop):
    """A generator that yields returns a number converted to a bytestring.
    It generates all bytes starting from the start value until stop (e.g. between 0 and 256^2
    It will return all bytes from x\00 to x\ff\xff, by returning first all the 1-byte sequences
     then all the 2-byte sequence. (Including both x\00 and x\00\x00)

    :param start: The first value that will be converted to a bytestring
    :param stop: The upper limit (Will not be returned by the generator)
    """
    number = start
    power = initialize_generator_power(number)
    reset_number = False
    while number < stop:
        while 256 ** power <= number:
            power += 1
            reset_number = True
        if power != 1 and reset_number:
            number = 0
            reset_number = False
        yield number.to_bytes(power, 'big')
        number += 1


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


def producer(queue, lock, producer_number, elements_per_producer, offset):
    """Inserts byte string values into a process safe queue.
    The producer won't close until all the elements in the queue are consumed
    :param queue: The queue where elements will be inserted
    :param lock: A protection mechanism between producer, consumer and mainprocess shared resources
    :param producer_number: The number of the producer in the producer list handled by
    the mainprocess. Used to split the elements between producers.
    :param elements_per_producer: The number of elements to be inserted
    :param offset: A number used to compute the first and last element that will be inserted by
    the current producer
    """
    with lock:
        print(f'Starting producer with PID {os.getpid()}')
    producer_start = offset + elements_per_producer * producer_number
    producer_stop = offset + elements_per_producer * (producer_number + 1)
    producer_generator = byte_generator(producer_start, producer_stop)
    print(f"Limits of the producer with PID {os.getpid()}:[{producer_start},{producer_stop}]")
    for i in range(elements_per_producer):
        queue.put(next(producer_generator))
    with lock:
        print(f'Closing producer {os.getpid()} after all elements were added to the queue')


def consumer(queue, lock, pipe_conn, corrupted_archive, file_name, file_hash, hash_method):
    """Reconstructs the corrupted archive by reading byte string elements from a process safe queue.
    If the archive can be reconstructed it sends the byte string to be used to the main process.
    If the archive can not be reconstructed it sends the Not found string.
    The consumer won't close until all the elements in the queue are consumed
    :param queue:  The queue from where elements will be read
    :param lock: A protection mechanism between producer, consumer and mainprocess shared resources
    :param pipe_conn: The communication pipe between consumer and mainprocess
    :param corrupted_archive: The name of the archive to be reconstructed
    :param file_name: The name of the file to be extracted from the archive
    :param file_hash: The hash of the file to be extracted from the archive
    :param hash_method: The method of generating the file_hash (any hashlib method sent as a string e.g. 'md5')
    """
    with lock:
        print(f'Starting consumer with PID {os.getpid()}')

    # Checks if we found a solution on this thread
    sent_value = 0
    queue_timeout = 3
    elements_processed = 0

    while not queue.empty():
        try:
            r_value = queue.get(timeout=queue_timeout)
            elements_processed += 1
            if elements_processed % 500 == 0:
                with lock:
                    print(
                        f"Consumer with PID {os.getpid()} processed f{elements_processed} elements. Queue remaining "
                        f"size:{queue.qsize()}")
            response = check_archive_validity(corrupted_archive, r_value, file_name, file_hash, hash_method)
            if response:
                with lock:
                    print(f"Consumer with PID {os.getpid()} found the file after adding:", r_value)
                    print(f'{os.getpid()} tries to send correct bytes missing')
                pipe_conn.send(r_value)
                sent_value = 1

                # We can't close the processes until all elements where consumed from the queue.
                # Therefore we empty it after finding the correct value
                # TODO!!!! At the moment only the processes that find the result are emptying the queue.
                # Add a shared value to notify all!
                while not queue.empty():
                    queue.get(timeout=1)

        # When we fail to extract an element from the queue
        except Empty:
            print(f"Consumer with PID {os.getpid()} found that the Queue was empty")
            if sent_value == 0:
                with lock:
                    print(f'Consumer with PID {os.getpid()} tries to send Not found signal (from exc)')
                pipe_conn.send("Not found")
            else:
                with lock:
                    print(f'Consumer with PID {os.getpid()} already sent results through pipe ')
    if sent_value == 0:
        with lock:
            print(f'Consumer with PID {os.getpid()} tries to send Not found signal (after while)')
        pipe_conn.send("Not found")


if __name__ == '__main__':
    archive_name = "./the.zip"
    file_name = 'LoremIpsum.txt'
    bytes_missing = 2
    hash_method = 'md5'

    file_hash = compute_hash_unopened_file(file_name, hash_method)

    queue = Queue()
    lock = Lock()

    current_bytes_try = 1
    numbers_of_producers = 4
    numbers_of_consumers = 4

    while True:
        offset = 256 ** (current_bytes_try - 1)
        if offset == 1:
            offset = 0
        elements_to_be_added = 256 ** current_bytes_try - offset
        # TODO: Check that numbers divide correctly
        elements_per_producer = int(
            elements_to_be_added / numbers_of_producers)

        producers = []
        consumers = []
        pipe_list = []

        main_corrupted_archive, removed_bits = trim_archive(archive_name, bytes_missing, copy=True,
                                                            c_name=f'MAIN_truncated_archive', save_bits=True)
        print("Bits that were removed:", removed_bits)
        print("Generator value for the removed part:", int.from_bytes(removed_bits, byteorder='big'))

        # Create producers processes
        for i in range(numbers_of_producers):
            producers.append(Process(target=producer, args=(queue, lock, i, elements_per_producer, offset)))

        # Create consumers processes
        for i in range(numbers_of_consumers):
            corrupted_archive = trim_archive(archive_name, bytes_missing, copy=True, c_name=f'tr_{i}')
            parent_conn, child_conn = Pipe()
            pipe_list.append(parent_conn)
            c = Process(target=consumer,
                        args=(queue, lock, child_conn, corrupted_archive, file_name, file_hash, hash_method))
            consumers.append(c)

        for p in producers:
            p.start()

        for c in consumers:
            c.start()

        for p in producers:
            p.join()
            print(f"Producer {p} finished the job")

        with lock:
            print(f'Main thread tries to gather results from processes')
        processes_responses = [x.recv() for x in pipe_list]

        for c in consumers:
            c.join()
            print(f"Consumer {c} finished the job")

        print("Results from processes:", processes_responses)
        for response in processes_responses:
            if response != 'Not found':
                append_bytes_to_file(main_corrupted_archive, response)
                print("File found after adding the following bits:")
                print(response)
                z = zipfile.ZipFile(main_corrupted_archive)
                f = z.open(file_name)
                f.seek(0)
                print("File content:")
                print(f.read())
                print("Done!")
                exit(0)
        print(f"Failed to unpack with {current_bytes_try}")
        current_bytes_try += 1
