import zipfile

from rarfile import RarFile

from file_processing import get_file_extension, compute_hash_unopened_file


def read_input_from_keyboard():
    # Archive name
    while True:
        archive_name=input("Provide the path to the archive:\n")
        file_extension = get_file_extension(archive_name)

        accepted_extensions = {'.zip': zipfile.ZipFile, '.rar': RarFile}
        if file_extension not in accepted_extensions:
            print("Please send a file with one of the following extensions:", list(accepted_extensions.keys()))
        try:
            with open(archive_name,'r') as f:
                archive_open_function = accepted_extensions[file_extension]
                break
        except FileNotFoundError:
            print("Archive does not exist. Please send a valid one")
        except Exception as e:
            print(e)

    # File name
    while True:
        file_name=input("Provide the path to the file:\n")
        try:
            with open(file_name,'r') as f:
                #Needs_password
                while True:
                    needs_password=input("Does the archive require a password? [Y/N]\n")
                    if needs_password=='Y':
                        needs_password=True
                        break
                    elif needs_password=='N':
                        needs_password=False
                        break
                    else:
                        print('Invalid option. Please respond with Y or N\n')
                #Password value
                if needs_password:
                    password=input("What is the password?\n")
                    z = archive_open_function(archive_name)
                    f = z.open(file_name, pwd=bytes(password, 'utf-8'))
                else:
                    password=None
                    z = archive_open_function(archive_name)
                    f = z.open(file_name)
                break
        except FileNotFoundError:
            print("File does not exist. Please send a valid one")
        except Exception as e:
            print(e)

    print("What is the number of bytes that you want to truncate from the archive?")
    bytes_missing=read_positive_integer()

    while True:
        try:
            hash_method=input("What is the hashing method that you want to use?\n")
            file_hash = compute_hash_unopened_file(file_name, hash_method)
            break
        except Exception as e:
            print(e)

    print("What is the number of producers that you want to use?")
    numbers_of_producers = read_positive_integer()

    print("What is the number of consumers that you want to use?")
    numbers_of_consumers = read_positive_integer()


    return archive_name,archive_open_function,file_name,needs_password,\
           password,bytes_missing,hash_method,file_hash,numbers_of_producers,\
           numbers_of_consumers


def read_positive_integer():
    while True:
        try:
            result=int(input())
            if result<=0:
                print("The number must be bigger than 0.")
                continue
            return result
            break
        except ValueError:
            print("Invalid input. Please give an integer")
        except Exception as e:
            print(e)