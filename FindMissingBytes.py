# Sa se scrie un tool care primeste un hash pentru un fisier originial si o arhiva trunchiata
# (maxim “x” bytes de la finalul arhivei originale lipsesc).
# Tool-ul va gasi fisierul original din arhiva
# ( in momentul in care se va despacheta fisierul din arhiva va avea acelasi hash ca cel primit la input )
# Pentru rezolvarea acestei probleme este imperativ folosirea oricarei forme de paralelizare (
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
import time

def trim_file(file,x):
    while True:
        try:
            f = open(file, 'r+b')
            f_size = f.seek(0, 2)
            f.seek(f_size - x, 0)
            # removed=f.read(x)
            # print(removed)
            # print(int.from_bytes(removed,byteorder='big'))
            # f.seek(f_size - x, 0)
            f.truncate()
            f.close()
        except Exception as e:
            print("An error occured in trim_ile")
            print(e)
            #traceback.print_exc()
            continue
        return file


def trim_archive(archive,x,copy=False,c_name='truncated_archive'):
    if copy==True:
        copy_name=f"{c_name}.{archive.split('.')[-1]}"
        shutil.copyfile(archive,copy_name) #create a copy of the archive
        return trim_file(copy_name,x)
    return trim_file(archive,x)


def get_hash(file,hash_type):
    m=hashlib.new(hash_type)
    with open(file, 'rb') as f:
        while chunk := f.read(1024):
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


def get_hash_zip(file,hash_type):
    m=hashlib.new(hash_type)
    while chunk := file.read(1024):
        m.update(chunk)
    return m.hexdigest()


#recompose_file(corrupted_archive,bits_missing,file_name,file_hash,hash_method)
def recompose_file(archive,bytes_to_add,file_name,file_hash,hash_method):
    added_bytes_length = append_bits_to_file(archive, bytes_to_add)
    try:
        z = zipfile.ZipFile(archive)
        # print(f"{file_name}")
        # print(file_name in z.namelist())
        f = z.open(file_name)
        computed_hash = get_hash_zip(f, hash_method)
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
            print("@@@@ NEW ERROR FOUND @@@")
            print(e)
            print(archive)
            traceback.print_exc()
            exit()
    finally:
        trim_archive(archive, added_bytes_length)



def producer(queue,lock,producer_number,elements_per_producer):
    with lock:
        print(f'Starting producer {os.getpid()}')
    #queue.cancel_join_thread()
    producer_generator=byte_generator(elements_per_producer*producer_number,elements_per_producer*(producer_number+1))
    print(elements_per_producer*producer_number,elements_per_producer*(producer_number+1))
    for i in range(elements_per_producer):

        element=next(producer_generator)
        # if element == b'\x03\x00\x00':
        #     print("Written in queue")
        # print(element)
        queue.put(element)
        #queue.put(next(producer_generator))
        # with lock:
        #     print(f"{os.getpid()} added {element} to the queue")
        #     print(f"{queue.qsize()}")
    with lock:
        print(f'Closing producer {os.getpid()}')


def consumer(queue,lock,pipe_conn,corrupted_archive,file_name,file_hash,hash_method):
    with lock:
        print(f'Starting consumer {os.getpid()}')

    sent_value=0

    while not queue.empty():
        try:
            r_value=queue.get(timeout=1)
            # print(r_value)
            # time.sleep(2)
            response=recompose_file(corrupted_archive,r_value,file_name,file_hash,hash_method)
            if response:
                print(f"{os.getpid()} found the file after adding:",r_value)
                # z = zipfile.ZipFile(corrupted_archive)
                # f = z.open(file_name)
                # f.seek(0)
                # print("File content:")
                # print(f.read())
                with lock:
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
            print(f"{os.getpid()} found that the Queue was empty")
            if sent_value==0:
                with lock:
                    print(f'{os.getpid()} tries to send not found signal in Empty')
                pipe_conn.send("Not found")
            else:
                with lock:
                    print(f'{os.getpid()} already sent results through pipe ')
    if sent_value == 0:
        with lock:
            print(f'{os.getpid()} tries to send not found signal after while')
        pipe_conn.send("Not found")
    return 0


if __name__ == '__main__':
    archive_name="./the.zip"
    file_name='LoremIpsum.txt'
    bits_missing=2
    hash_method='md5'
    file_hash=get_hash(file_name,hash_method)

    queue=Queue()
    lock=Lock()
    elements_to_be_added=256**bits_missing
    numbers_of_producers=4
    elements_per_producer=int(elements_to_be_added/numbers_of_producers) ### TODO: Check that numbers divide correctly
    numbers_of_consumers=4


    producers=[]
    consumers=[]
    pipe_list=[]

    main_corrupted_archive=trim_archive(archive_name,bits_missing,copy=True,c_name=f'MAIN_truncated_archive')

    for i in range(numbers_of_producers):
        producers.append(Process(target=producer,args=(queue,lock,i,elements_per_producer)))

    for i in range(numbers_of_consumers):
        corrupted_archive=trim_archive("./the.zip",bits_missing,copy=True,c_name=f'tr_{i}')
        parent_conn,child_conn=Pipe()
        pipe_list.append(parent_conn)
        c=Process(target=consumer,args=(queue,lock,child_conn,corrupted_archive,file_name,file_hash,hash_method))
        consumers.append(c)

    for p in producers:
        p.start()

    for c in consumers:
        c.start()

    for p in producers:
        print(p.join(),"Producer left")

    with lock:
        print(f'I try to read values from children')

    processes_responses=[x.recv() for x in pipe_list]

    for c in consumers:
        print(c.join(),"Consumer left")

    print(processes_responses)
    for response in processes_responses:
        if response!='Not found':
            append_bits_to_file(main_corrupted_archive, response)
            print("File found after adding the following bits:")
            print(response)
            z = zipfile.ZipFile(main_corrupted_archive)
            f = z.open(file_name)
            f.seek(0)
            print("File content:")
            print(f.read())
            print("Done!")
            break

