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
import zipfile
from multiprocessing import Process, Queue, Lock, Pipe, Value
from time import sleep

from rarfile import RarFile

from consumer_producer_model import producer, consumer
from file_processing import trim_archive, compute_hash_unopened_file, append_bytes_to_file, get_file_extension


def create_producers(number_of_producers, queue, lock, current_bytes_try, found):
    """Creates a list of producers that share a queue and a lock.
    The producers create data for the consumers in the consumer producer model

    :param number_of_producers: The number of producers that will add to the queue
    :param queue: The process safe queue that will be shared among producers/consumers and main process
    :param lock: The lock over resources that will be shared among producers/consumers and main process
    :param current_bytes_try: The length of the byte sequence to be generated by the producers
    :return: A list of producer processes that can be started
    :param found: A shared variable  between consumer/producer and mainprocess
    """
    # Create producers processes

    offset = 256 ** (current_bytes_try - 1)
    if offset == 1:
        offset = 0
    elements_to_be_added = 256 ** current_bytes_try - offset
    # TODO: Check that numbers divide correctly
    elements_per_producer = int(
        elements_to_be_added / numbers_of_producers)

    producers = []

    for i in range(numbers_of_producers):
        producers.append(Process(target=producer, args=(queue, lock, i, elements_per_producer, offset, found)))
    return producers


def create_consumers_and_pipes(number_of_consumers, archive_name, bytes_missing, queue, lock, file_name,
                               file_hash, hash_method, found, archive_function, needs_password=False, password=None):
    """Creates a list of consumers that share a queue and a lock.
    Creates a list of pipes used for communication between consumers and main process

    :param number_of_consumers: The number of producers that will read to the queue
    :param archive_name: The name of the archive to be reconstructed by consumers
    :param bytes_missing: The number of bytes to be trimmed from the archive
    :param queue: The process safe queue that will be shared among producers/consumers and main process
    :param lock: The lock over resources that will be shared among producers/consumers and main process
    :param file_name: The name of the file to be extracted from the archive
    :param file_hash: The hash of the file to be extracted from the file
    :param hash_method: The hash method (any hashlib method sent as a string e.g. 'md5')
    :return: A list of consumers that can be started, A list of pipes used for communication between consumers and main process
    :param found: A shared variable  between consumer/producer and mainprocess
    in order to stop the process when the solution is found
    :param archive_function: A function that will be used to open the archive
    :param needs_password: A boolean value telling if a password is needed to open the archive. (default False)
    :param password: String representation of the password (default False)
    """
    # Create consumers processes

    consumers = []
    pipe_list = []

    for i in range(numbers_of_consumers):
        corrupted_archive = trim_archive(archive_name, bytes_missing, copy=True, c_name=f'tr_{i}')
        parent_conn, child_conn = Pipe()
        pipe_list.append(parent_conn)
        c = Process(target=consumer,
                    args=(queue, lock, child_conn, corrupted_archive, file_name, file_hash,
                          hash_method, found, archive_function, needs_password, password))
        consumers.append(c)
    return consumers, pipe_list


if __name__ == '__main__':

    # archive_name = "./the.zip"
    # file_name = 'LoremIpsum.txt'
    # needs_password = False
    # password = None

    # archive_name = "./AI_PROJECT.rar"
    # file_name = 'AI_PROJECT/news.json'
    # needs_password=False
    # password=None

    # archive_name = "./the_pass_protected.zip"
    # file_name = 'LoremIpsum.txt'
    # needs_password=True
    # password='qweasdzxc1'

    archive_name = "./the_pass_protected.rar"
    file_name = 'LoremIpsum.txt'
    needs_password = True
    password = 'qweasdzxc1'

    bytes_missing = 2
    hash_method = 'md5'

    file_hash = compute_hash_unopened_file(file_name, hash_method)
    file_extension = get_file_extension(archive_name)

    accepted_extensions = {'.zip': zipfile.ZipFile, '.rar': RarFile}
    if file_extension not in accepted_extensions:
        print("Please send a file with one of the following extensions:", list(accepted_extensions.keys()))
        exit()

    archive_open_function = accepted_extensions[file_extension]

    queue = Queue()
    lock = Lock()
    numbers_of_producers = 4
    numbers_of_consumers = 4
    found = Value('i', 0)

    current_bytes_try = 1
    while True:

        main_corrupted_archive, removed_bits = trim_archive(archive_name, bytes_missing, copy=True,
                                                            c_name=f'MAIN_truncated_archive', save_bytes=True)
        print("Bits that were removed:", removed_bits)
        print("Generator value for the removed part:", int.from_bytes(removed_bits, byteorder='big'))

        producers = create_producers(numbers_of_producers, queue, lock, current_bytes_try, found)
        consumers, pipe_list = create_consumers_and_pipes(numbers_of_consumers, archive_name, bytes_missing, queue,
                                                          lock, file_name, file_hash, hash_method, found,
                                                          archive_open_function, needs_password, password)
        for p in producers:
            p.start()

        sleep(1)

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

        # Check if we received a Wrong password message and restart with a new password
        if 'Wrong password' in processes_responses:
            print(f"The password provided was wrong! ")
            password = input("Please give a new password:\n")
            found.value = 0
            continue

        # Search for solution
        for response in processes_responses:
            if response != 'Not found':
                append_bytes_to_file(main_corrupted_archive, response)
                print("File found after adding the following bits:")
                print(response)
                z = archive_open_function(main_corrupted_archive)
                if needs_password:
                    f = z.open(file_name, pwd=bytes(password, 'utf-8'))
                else:
                    f = z.open(file_name)
                f.seek(0)
                print("File content:")
                print(f.read())
                print("Done!")
                exit(0)
        print(f"Failed to unpack with {current_bytes_try}")
        current_bytes_try += 1
