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
from multiprocessing import Process, Queue, Lock,Pipe
from queue import Empty
import traceback


def trim_file(file,x,save_bits=False):
    while True:
        try:
            f = open(file, 'r+b')
            f_size = f.seek(0, 2)
            f.seek(f_size - x, 0)
            if save_bits:
                removed = f.read(x)
                f.seek(f_size - x, 0)
            f.truncate()
            f.close()
        except Exception as e:
            print("An error occured in trim_file")
            print(e)
            continue
        if save_bits:
            return file,removed
        return file


def trim_archive(archive,x,copy=False,c_name='truncated_archive',save_bits=False):
    if copy==True:
        copy_name=f"{c_name}.{archive.split('.')[-1]}"
        shutil.copyfile(archive,copy_name) #create a copy of the archive
        if save_bits:
            return trim_file(copy_name,x,save_bits)
        return trim_file(copy_name,x)
    return trim_file(archive,x)


def get_hash_unopened_file(file, hash_type):
    with open(file, 'rb') as f:
        return get_hash_opened_file(f, hash_type)


def get_hash_opened_file(file, hash_type):
    m=hashlib.new(hash_type)
    while chunk := file.read(1024):
        m.update(chunk)
    return m.hexdigest()


def initialize_generator_power(number):
    pow=1
    while 256**pow<=number:
        pow+=1
    return pow


def byte_generator(start,n):
    number=start
    pow=initialize_generator_power(number)
    reset_number=False
    while number<n:
        while 256**pow<=number:
            pow+=1
            reset_number=True
        if pow!=1 and reset_number:
            number=0
            reset_number=False
        yield number.to_bytes(pow,'big')
        number+=1


def append_bits_to_file(file,bits):
    f=open(file,'ab')
    f.write(bits)
    f.close()
    return len(bits)


def recompose_file(archive,bytes_to_add,file_name,file_hash,hash_method):
    added_bytes_length = append_bits_to_file(archive, bytes_to_add)
    try:
        z = zipfile.ZipFile(archive)
        f = z.open(file_name)
        computed_hash = get_hash_opened_file(f, hash_method)
        if computed_hash==file_hash:
            return True
        return False
    except Exception as e:
        ## TODO check other exception type
        ### BadZipFile when the archive is corrupted
        ### Errno 22 when the archive is valid but the file inside is corrupted
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


def producer(queue,lock,producer_number,elements_per_producer,offset):
    with lock:
        print(f'Starting producer with PID {os.getpid()}')
    producer_start=offset+elements_per_producer*producer_number
    producer_stop=offset+elements_per_producer*(producer_number+1)
    producer_generator=byte_generator(producer_start,producer_stop)
    print(f"Limits of the producer with PID {os.getpid()}:[{producer_start},{producer_stop}]")
    for i in range(elements_per_producer):
        queue.put(next(producer_generator))
    with lock:
        print(f'Closing producer {os.getpid()} after all elements were added to the queue')


def consumer(queue,lock,pipe_conn,corrupted_archive,file_name,file_hash,hash_method):
    with lock:
        print(f'Starting consumer with PID {os.getpid()}')

    ### Checks if we found a solution on this thread
    sent_value=0
    QUEUE_TIMEOUT=3
    elements_processed=0

    while not queue.empty():
        try:
            r_value=queue.get(timeout=QUEUE_TIMEOUT)
            elements_processed+=1
            if elements_processed%500==0:
                with lock:
                    print(f"Consumer with PID {os.getpid()} processed f{elements_processed} elements. Queue remaining size:{queue.qsize()}")
            response=recompose_file(corrupted_archive,r_value,file_name,file_hash,hash_method)
            if response:
                with lock:
                    print(f"Consumer with PID {os.getpid()} found the file after adding:",r_value)
                    print(f'{os.getpid()} tries to send correct bytes missing')
                pipe_conn.send(r_value)
                sent_value=1

                ### We can't close the processes until all elements where consumed from the queue.
                # Therefore we empty it after finding the correct value
                #### TODO!!!! At the moment only the processes that find the result are emptying the queue. Add a shared value to notify all!
                while not queue.empty():
                    queue.get(timeout=1)

        ### When we fail to extract an element from the queue
        except Empty:
            print(f"Consumer with PID {os.getpid()} found that the Queue was empty")
            if sent_value==0:
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
    return 0


if __name__ == '__main__':
    archive_name="./the.zip"
    file_name='LoremIpsum.txt'
    bytes_missing=3
    hash_method='md5'

    file_hash=get_hash_unopened_file(file_name, hash_method)

    queue=Queue()
    lock=Lock()

    current_bytes_try=1
    numbers_of_producers = 4
    numbers_of_consumers = 4

    while True:
        offset = 256 ** (current_bytes_try - 1)
        if offset==1:
            offset=0
        elements_to_be_added = 256 ** (current_bytes_try)-offset


        elements_per_producer = int(
            elements_to_be_added / numbers_of_producers)  ### TODO: Check that numbers divide correctly

        producers = []
        consumers = []
        pipe_list = []

        main_corrupted_archive, removed_bits = trim_archive(archive_name, bytes_missing, copy=True,
                                                            c_name=f'MAIN_truncated_archive', save_bits=True)
        print("Bits that were removed:", removed_bits)
        print("Generator value for the removed part:", int.from_bytes(removed_bits, byteorder='big'))

        ### Create producers processes
        for i in range(numbers_of_producers):
            producers.append(Process(target=producer, args=(queue, lock, i, elements_per_producer,offset)))

        ### Create consumers processes
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
                append_bits_to_file(main_corrupted_archive, response)
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
        current_bytes_try+=1



