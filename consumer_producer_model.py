import os
from queue import Empty

from file_processing import check_archive_validity
from generator import byte_generator


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