# Sa se scrie un tool care primeste un hash pentru un fisier originial si o arhiva trunchiata (maxim “x” bytes de la finalul arhivei originale lipsesc).
# Tool-ul va gasi fisierul original din arhiva ( in momentul in care se va despacheta fisierul din arhiva va avea acelasi hash ca cel primit la input )
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
import shutil
import zipfile
import itertools


def trim_file(file,x):
    f = open(file, 'r+b')
    f_size = f.seek(0, 2)
    f.seek(f_size - x, 0)
    # removed=f.read(x)
    # print(removed)
    # print(int.from_bytes(removed,byteorder='big'))
    # f.seek(f_size - x, 0)
    f.truncate()
    f.close()
    return file


def trim_archive(archive,x,copy=False):
    if copy==True:
        copy_name=f"truncated_archive.{archive.split('.')[-1]}"
        shutil.copyfile(archive,copy_name) #create a copy of the archive
        return trim_file(copy_name,x)
    return trim_file(archive,x)

### TODO refactor this an get_hash_zip in a single function
def get_hash(file,hash_type):
    m=hashlib.new(hash_type)
    with open(file, 'rb') as f:
        while chunk := f.read(1024):
            m.update(chunk)
    return m.hexdigest()


def get_hash_zip(file,hash_type):
    m=hashlib.new(hash_type)
    while chunk := file.read(1024):
        m.update(chunk)
    return m.hexdigest()


def append_bits_to_file(file,bits):
    f=open(file,'ab')
    f.write(bits)
    f.close()
    return len(bits)


def generate_byte_string(length):
    all_bytes=[e.to_bytes(1,'big') for e in range(256)]
    if length==1:
        return all_bytes
    else:
        all_n_bytes=[b"".join(e) for e in itertools.product(all_bytes,repeat=length)]


def initialize_generator_power(number):
    pow=0
    while 256**pow<=number:
        pow+=1
    return pow


def byte_generator(n):
    number=0
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


def recompose_file(archive,filename,hash):
    i = 0
    found=False
    while not found:
        bytes_to_add=next(generator)
        added_bytes_length = append_bits_to_file(archive, bytes_to_add)
        try:
            z = zipfile.ZipFile(archive)
            f = z.open(filename)
            hash2 = get_hash_zip(f, 'md5')
            print(hash2)
            if hash2==hash:
                found=True
                print("File found after adding the following bits:")
                print(bytes_to_add)
                f.seek(0)
                print("File content:")
                print(f.read())
                exit()
        except Exception as e:
            ## TODO check other exception type
            if type(e).__name__ == 'BadZipFile':
                pass
            else:
                print(type(e).__name__)
        finally:
            trim_archive(archive, added_bytes_length)
            i += 1
            if i % 500 == 0:
                print(i)
                print("Last processed:",bytes_to_add)


BITS_TRIMMED=2
file_to_recompose='LAB4.txt'
corrupted_archive=trim_archive("./the.zip",BITS_TRIMMED,copy=True)
generator=byte_generator(2**200)

hash=get_hash(file_to_recompose,'md5')
print(hash)
print(corrupted_archive)

recompose_file(corrupted_archive,file_to_recompose,hash)

