import shutil
import os
import datetime
import logging
import subprocess

#Consts
DATE_FORMAT = "%Y-%m-%d"
DAYS_UNTIL_DELETE = 30

def main():

    ####################################################################

    #Source path info
    source_directory =  r"/home/data/nextcloud_data"
    database_directory = r"/var/lib/mysql/nextcloud_db"

    #Target path info
    target_base_directory = r"/home/data/nextcloud_backup"
    log_directory = r"/home/data/nextcloud_backup/log"

    #Database (mysql) info
    database_username = "root"
    database_password = "superSecretDbPassword"
    database_name = "nextcloud_db"
    
    #Log info
    log_level = logging.WARNING

    ####################################################################



    #Start of Backup-Skript
    datetime_now = datetime.datetime.now()
    datetime_now_string = datetime_now.strftime(DATE_FORMAT)
    
    if try_create_directory(log_directory) is False:
        return

    log_file = os.path.join(log_directory, datetime_now_string + ".txt")

    #Logging settings
    logging.basicConfig(filename=log_file,level=log_level)

    #Check if target base diretory exists
    if try_create_directory(target_base_directory) is False:
        logging.error("Can not create direcotry " + target_base_directory)
        return

    #Auto Gen Variablen
    target_directory = os.path.join(target_base_directory, datetime_now_string)

    #Get source directory sizes
    uncompressed_source_directory_size = get_directory_size(source_directory)  
    uncompressed_database_size = get_directory_size(database_directory)

    #Maximum space needed for backup + 10mb for safety
    total_needed_space = uncompressed_source_directory_size + uncompressed_database_size + 10000000
 
    #Remove old directories
    delete_old_directories(target_base_directory)
    
    #Get available space on disk
    free_space = shutil.disk_usage(target_base_directory).free

    #Delte oldes if disk space is 
    if free_space <= total_needed_space:
        logging.info("Try making more space")
        #Try making enough space 
        make_enough_space_for_new_backup(target_base_directory, total_needed_space)
        
    #Create new Backup directory
    if try_create_directory(target_directory) is False:
        logging.error("Can not create directory, the user may have not enough rights")
        return

    #Create Data-Zip
    if create_data_backup(source_directory, target_directory) is False:
        logging.error("Data backup failed")

    #Create sql dump
    if create_mysql_dump(database_username, database_password, database_name, target_directory) is False:
        logging.error("Database backup failed")

    #Remove empty log file
    if (os.stat(log_file).st_size == 0):
        os.remove(log_file)

def create_mysql_dump(database_username, database_password, database_name, target_directory):
    try:    
        #Start mysqldump to create a safe backup 
        subprocess.check_call("mysqldump -u %s -p%s -h %s -e --opt -c %s | gzip -c > %s.gz" % 
            (database_username, database_password, "localhost", database_name, os.path.join(target_directory, "db")), shell=True)    

        return True
    except Exception as e: 
        logging.error(str(e))
        return False


def create_data_backup(source_directory, target_directory):
    try:
        shutil.make_archive(os.path.join(target_directory, "data"), 'zip', source_directory)
        return True
    except Exception as e: 
        logging.error(str(e))
        return False


def make_enough_space_for_new_backup(target_path, requiertSpace):
    directory_list = []
    for current_dir_tuple in os.walk(target_path):
        current_dir = current_dir_tuple[0]

        #Skip root directory
        if current_dir == target_path:
            continue

        directory_name = os.path.basename(current_dir)

        #Convert directory name to date
        date_of_current_folder = date_from_string(directory_name)
    
        #Skipping other folders
        if date_of_current_folder is None:            
            continue
        
        #Fill the list of backup directories
        directory_list.append((current_dir, date_of_current_folder))

    #Sort list by date, so out loop start with the oldest
    directory_list = sorted(directory_list, key=lambda x: x[1])

    generated_space = 0
    for current_dir_tuple in directory_list:       
        current_dir = current_dir_tuple[0]        
        #Get size of the directory we are going to delete
        space_of_current_dir = get_directory_size(current_dir)

        #Delete directory
        if try_delete_directory(current_dir) is True:
            generated_space += space_of_current_dir

        #If there is enough space we can cancel the loop
        if generated_space > requiertSpace:
            return


def delete_old_directories(target_path):     
    current_date = datetime.datetime.now().date()

    for current_dir_tuple in os.walk(target_path):
        current_dir = current_dir_tuple[0]

        #Root directory überspringen
        if current_dir == target_path:
            continue

        directory_name = os.path.basename(current_dir)

        #Convert directory name to date
        date_of_current_folder = date_from_string(directory_name)
    
        if date_of_current_folder is None:            
            logging.info("Unkown directory in target base path " + current_dir)
            continue
         
        #Get age of directory
        age_of_folder = (current_date - date_of_current_folder).days
       
        #Check if directory is ready to die
        if age_of_folder <= DAYS_UNTIL_DELETE:
            continue

        #Delete old directory
        if try_delete_directory(current_dir) is False:
            #Directry delete failed 
            logging.warning("Can not delete " + current_dir)       

    return


def try_create_directory(target_path): 
    try:
        if not os.path.exists(target_path):
            os.makedirs(target_path) 
        return True
    except Exception as e: 
        logging.error(str(e))
        return False

def try_delete_directory(directory_path):
    try:
        shutil.rmtree(directory_path)
        return True
    except Exception as e: 
        logging.error(str(e))
        return False

def date_from_string(directory_name): 
    try:
        return datetime.datetime.strptime(directory_name, DATE_FORMAT).date()
    except:
        return None


def get_directory_size(directory_path): 
    total = 0
    for entry in os.scandir(directory_path):
        if entry.is_dir(follow_symlinks=False):
            total += get_directory_size(entry.path)
        else:
            total += entry.stat(follow_symlinks=False).st_size    
    return total


if __name__ == "__main__":
    main()