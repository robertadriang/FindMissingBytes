import os
import time
from multiprocessing import Process, Queue, Lock,Pipe
from queue import Empty
from multiprocessing.pool import ThreadPool

def producer(queue, lock, elements):
    with lock:
        print(f'Starting producer {os.getpid()}')

    for element in elements:
        queue.put(element)

    with lock:
        print(f'Closing producer {os.getpid()}')

def consumer(queue,lock,pipe_conn):
    with lock:
        print(f'Starting consumer {os.getpid()}')

    sum=0
    while True:
        try:
            r_value=queue.get(timeout=3)
            sum += r_value
        except Empty:
            print("Queue was empty")
            pipe_conn.send(sum)
            exit()
        with lock:
            print('{} got {}'.format(os.getpid(), r_value))

    with lock:
        print(f'Consumer {os.getpid()} computed {sum}')


if __name__ =='__main__':
    queue=Queue()
    lock=Lock()

    #### Generate queue
    elements_to_be_added=1000000
    number_of_producers=5
    elements_per_list=int(elements_to_be_added/number_of_producers) ### TODO: Check that numbers divide correctly
    elements_of_queue=[[e for e in range(elements_per_list*i,elements_per_list*(i+1))] for i in range(number_of_producers)]

    producers=[]
    consumers=[]
    pipe_list=[]

    for i in elements_of_queue:
        producers.append(Process(target=producer,args=(queue,lock,i)))

    for i in range(10):
        parent_conn,child_conn=Pipe()
        pipe_list.append(parent_conn)
        c=Process(target=consumer,args=(queue,lock,child_conn))
        #c.daemon=True
        consumers.append(c)

    for p in producers:
        p.start()

    for c in consumers:
        c.start()

    for p in producers:
        res=p.join()

    for c in consumers:
        c.join()

    sum_read=sum([x.recv() for x in pipe_list])
    sum_written=elements_to_be_added*(elements_to_be_added-1)/2
    print("Sum of read numbers from workers:",sum_read)
    print("Sum of written numbers to workers:", sum_written)

    print("Parent process will close")
