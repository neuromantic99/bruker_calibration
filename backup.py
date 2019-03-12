'''
backup.py
Lloyd Russell 2016/7

File conversion and backup management utility for Bruker/Prairie View acquisition machines

This script does the following:
* Convert PrairieView RAW files
* Convert folders of single page TIFFs into multipage TIFFs
* Then delete those single TIFFs (but keep XML files)
* Backup to server

Notes:
* One Image-Block Ripping Utility instance will be opened for each SOURCES drive listed in
  configuration section below (if files are found that need to be converted)
* Single TIFFs are only deleted if: the flag to delete is set to true (default) and if
  after writing the MPTIFF, it can be closed and reopened successfully and if the number of
  frames contained within it is the same as the original single tiffs, and if the file size
  in bytes is the same as or larger than the original tiffs
* Log files are kept in C:/BackupLogs for the RAW-conversion and the MPTIFF-combining, as
  well as the transfer to the server
* Transfer to the server is done via ROBOCOPY
* Source folder -> server mappings are defined in the SERVER_MAPPINGS dictionary
* See problems below. Briefly, RAW files will be converted immediately, but those folders not backed up
  to ensure no single page tiffs are inadvertently copied over. The converted RAW files
  will be combined into a MPTIFF and transferred on the next run (i.e. usually the next day)

To use:
* Run manually (see below)
* Or, create BAT file and use Task Scheduler to automate (use options like only run if idle for X minutes)

Command line options:
Used to enable/disable options, or to restrict the file search to match a given string
-search : 'string'
-combinetiffs : 'int' (0 or 1)
-deletetiffs : 'int' (0 or 1)
-convertraw : 'int' (0 or 1)
-backup : 'int' (0 or 1)

Manual example from Windows command line (normal usage):
  python3 backup.py

Manual example (with optional command line arguments):
  python3 backup.py -search Lloyd/2017 -deletetiffs 0 -backup 0
    To: 1) only process 'Lloyd/2017...' folders, 2) NOT delete single tiffs, and 3) NOT backup to server

Future possibilities:
* Motion correct? (probably not)
* Save all movies as binary format? or other format HDF5 etc....
* Compression? (zip etc, probably no need and it'll be a hassle to decompress before use)
* Delete files from local machine (perhaps delete files older than e.g. 7 days)

Problems:
* ImageBlock Rip Utility is an external program running asynchronously and cannot communicate
  with this script. The only way to backup converted RAW files is to have a listener script that
  runs and detects when a conversion has finished by looking for absense of the RAWDATA files and
  the Filelist.txt file.
  The alternative is to just backup the converted file the following day... which seems the best option currently.
* ImageBlock utility can only convert files saved with SAME version of PrairieView (this shouldn't be a problem)
'''

import argparse
import os
import subprocess
import time
import datetime
import glob
import re
import psutil
import sys
import getopt
import warnings
from skimage.external import tifffile
import xml.etree.ElementTree

# disable warnings
warnings.filterwarnings('ignore')  # tifffile gives ugly unneccessary warnings

# enable printing colours to command window
from colorama import init
from termcolor import colored
init()


# CONFIGURATION
# =============

# defaults
DO_COMBINE = True
DELETE_SINGLE_TIFFS = True
DO_CONVERT_RAW = True
DO_BACKUP = True
SEARCH_STRING = None
                 

# parse command line inputs
parser = argparse.ArgumentParser()
parser.add_argument("-search", help="Restrict file search to include specified string? (e.g. User's name, or particular date)", type=str)
parser.add_argument("-convertraw", help="Convert RAWDATA to TIFFs?", type=int)
parser.add_argument("-combinetiffs", help="Combine single TIFFs into MPTIFF?", type=int)
parser.add_argument("-deletetiffs", help="Delete single TIFFs after combining to MPTIFF?", type=int)
parser.add_argument("-backup", help="Backup to server?", type=int)
args = parser.parse_args()

if not args.convertraw == None:
    DO_CONVERT_RAW = args.convertraw
if not args.combinetiffs == None:
    DO_COMBINE = args.combinetiffs
if not args.deletetiffs == None:
    DELETE_SINGLE_TIFFS = args.deletetiffs
if not args.backup == None:
    DO_BACKUP = args.backup
if not args.search == None:
    SEARCH_STRING = args.search

# drive locations
# PC_DETAILS = {
    # 'PRAIRIE'   : ['USERBRU-6GQ0VDF', ['E:/Data','F:/Data']],
    # 'ZOO'       : ['ZOO-PC',          ['C:/Data', 'C:/git/PyBehaviour/Results']],
    # 'OPTIPLEX'  : ['HAUSSERLAB-PC',   ['D:/Data']],
    # 'BRUKER2-PC1': ['BRUKER2-PC1', ['E:/Data','F:/Data']],
    # 'BRUKER2-PC2': ['BRUKER2-PC2', ['C:/Data', 'C:/git/PyBehaviour/Results']]
# }

PC_DETAILS = {'PACKER1' : ['PACKER1', [r'F:\Data\\']]}

# match this computer name to known aliases
this_pc_name = None
this_pc_id = os.environ['COMPUTERNAME']
for key, values in PC_DETAILS.items():
    pc_id = values[0]
    if pc_id == this_pc_id:
        this_pc_name = key
if this_pc_name == None:
    print(colored('Sorry, this computer is not recognised. Goodbye.', 'white', 'on_red'))
    time.sleep(1)
    exit()
print('This is ' + colored(this_pc_name, 'grey', 'on_yellow') + colored(' (' + this_pc_id + ')', 'yellow'))

SOURCES = PC_DETAILS[this_pc_name][1]
DESTINATION = r'Z:\*\Data'  # research data
# DESTINATION = '//128.40.202.172/*/Data/'  # rackstation
SERVER_MAPPINGS = {'Jimmy'  : 'jrowland',
                   'Adam'   : 'apacker',
                   'Rob'    : 'rlees', 
                   'Ankit'  : 'aranjan',
                   'AdamH'  : 'aharris'                   
                  } 
                  

# other paths
if not os.path.exists('C:/BackupLogs/'):
    os.makedirs('C:/BackupLogs/')
CONVERT_LOGFILE = 'C:/BackupLogs/' + '{:%Y%m%d_%H%M%S}'.format(datetime.datetime.now()) + '.txt'
ROBOCOPY_LOGFILE = 'C:/BackupLogs/' + '{:%Y%m%d_%H%M%S}'.format(datetime.datetime.now()) + '_ROBOCOPY.txt'

IGNORE = ['$RECYCLE.BIN', 'System Volume Information']
IMAGEBLOCKRIPPER = 'C:/Program Files/Prairie/Prairie View/Utilities/Image-Block Ripping Utility.exe'



# FUNCTIONS
# =========

def select_folder():
    ''' This isn't currently used. It could be used to select with a 'GUI' a single folder to process... '''
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory()


def convert_raw_to_tiff(file_list):
    # because of the way image-block ripper works we have to open two instances of it - one for
    # each data drive and let it walk through them building it's own file lists.
    # this doesn't seem to be a problem
    # the input 'filelist' is only used to test whether it's neccessary to call the utility for that drive

    for src in SOURCES:
        if any(src in s for s in file_list):
            subprocess.Popen([IMAGEBLOCKRIPPER, "-IncludeSubFolders", "-AddRawFileWithSubFolders", src, "-Convert"])


# function definitions
def convert_to_mptiff(file_list):
    '''
    This function is responsible for converting a folder of single page TIFFs into MPTIFFs
    It takes as input a list of files (genrally all TIFFs within one folder)
    It then splits the files up into matching 'Channel' and 'Cycle' sets and combines those into MPTIFFs
    '''

    fullpath = os.path.dirname(file_list[0])
    folder_name = os.path.basename(fullpath)
    drive_name = os.path.splitdrive(fullpath)[0]
 
    # find number of channels in this acquisition
    channel_string_matches = [re.search('_Ch([0-9])', s).group() for s in file_list if re.search('_Ch([0-9])', s)]
    diff_channels = sorted(set(channel_string_matches))
    num_channels = len(diff_channels)

    # find number of cycles in this acquisition
    cycle_string_matches = [re.search('_Cycle([0-9]{5})', s).group() for s in file_list if re.search('_Cycle([0-9]{5})', s)]
    diff_cycles = sorted(set(cycle_string_matches))
    num_cycles = len(diff_cycles)
    
    print(fullpath)

    for cycle in range(num_cycles):
        for channel in range(num_channels):
                        
            cycle_num_str = diff_cycles[cycle]
            channel_num_str = diff_channels[channel]

            matching_files = [s for s in file_list if cycle_num_str in s and channel_num_str in s]
            mptiff_name =  folder_name + cycle_num_str + channel_num_str + '.tif'
            mptiff_path = os.path.join(fullpath, mptiff_name)
            
            # check if enough available disk space
            num_frames = len(matching_files)
            test_image = tifffile.imread(matching_files[0], multifile=False)
            im_dims = test_image.shape
            im_dtype = test_image.dtype
            pixel_size_bytes = test_image[0,0].nbytes  # test the size of first pixel, should be 2 for uint16
            free_space = psutil.disk_usage(fullpath).free  # in bytes
            estimated_size = im_dims[0] * im_dims[1] * num_frames * pixel_size_bytes
            
            print('   ' + mptiff_name + ' - ' + str(num_frames) + ' frames')

            # write single images to mptiff
            if free_space > estimated_size:
                with tifffile.TiffWriter(mptiff_path, bigtiff=True) as tif:
                    for i, frame in enumerate(matching_files):
                        with tifffile.TiffFile(frame, multifile=False) as input_tif:
                            data = input_tif.asarray()
                        tif.save(data)
                        msg = '   Writing frame: ' + str(i+1) + ' of ' + str(num_frames)
                        print(msg, end='\r')


                # check size of finished mptiff
                statinfo = os.stat(mptiff_path)
                mptiff_size_bytes = statinfo.st_size
            
                # try opening the mptiff
                try:
                    with tifffile.TiffFile(mptiff_path, multifile=False) as mptiff:
                        TEST_file_opened = True
                        TEST_filesize = len(mptiff)
                except:
                    TEST_file_opened = False
                    TEST_filesize = None

                # if things are ok, delete the single frame images
                if DELETE_SINGLE_TIFFS:
                    if TEST_file_opened and TEST_filesize==num_frames and mptiff_size_bytes>=estimated_size:
                        print('      Deleting single frames')
                        for frame in matching_files:
                            os.remove(frame)
                    else:
                        print('*** WARNING! FAILSAFE INITIATED! SAFTEY CHECKS FAILED! ***')
                        print('delete flag:',DELETE_SINGLE_TIFFS, 'test open:',TEST_file_opened, 'test frames:',TEST_filesize==num_frames, 'test bytes:',mptiff_size_bytes>=estimated_size)
            else:
                print('*** WARNING! NOT ENOUGH DISK SPACE! ***')    

    # must rename XML file otherwise imageJ reader gets confused by it
    xml_file = os.path.join(fullpath, folder_name + '.xml')
    if os.path.isfile(xml_file):
        os.rename(xml_file, xml_file.replace('.xml','_BACKUP.xml'))


def get_listing(root):
    '''
    This function walks through the drives specified in 'SOURCES' and will return the folders which:
        1) Are likley PrairieView acquistion folders based on presence on the ENV and XML files
        And are divided up into those that:
        1) contain RAWDATA and Filelist.txt files (which will need to be converted)
        2) contain multiple tiff files (which may need to be combined)
    '''
    print('Getting file listing of ' + colored(root,'cyan'))

    convert_from_raw_list = []
    convert_to_mptiff_list = []

    for dirname, dirnames, filenames in os.walk(root):
        for subdirname in dirnames:
            if subdirname not in IGNORE:
                # get folder contents
                fullpath = os.path.join(dirname, subdirname)
                if SEARCH_STRING == None or (not SEARCH_STRING == None and SEARCH_STRING in fullpath):
                    dirlisting = os.listdir(fullpath)

                    # if folder contains .xml and .env files of same name as folder this is a PV acquisition folder
                    if subdirname+'.env' in dirlisting and (subdirname+'.xml' in dirlisting or subdirname+'_BACKUP.xml' in dirlisting):
                        # print('  ' + str(len(dirlisting)) + ' files')

                        # if folder contains a Filelist.txt and RAW files, convert them to tiffs
                        found_raw_files = [os.path.join(fullpath, s) for s in dirlisting if '_RAWDATA_' in s]
                        found_filelists = [os.path.join(fullpath, s) for s in dirlisting if '_Filelist.txt' in s]
                        if found_filelists and found_raw_files:
                            convert_from_raw_list.append(fullpath)

                        else: # if > 10? tiff files found, combine them into MPTIFFs
                            tiff_list = glob.glob(os.path.join(fullpath, '*.ome.tif'))
                            tiff_list = sorted(tiff_list)

                            if len(tiff_list) > 3:
                                # check to see if this is an 'atlas imaging' acquisition
                                atlas_volume = False

                                xml_file = glob.glob(os.path.join(fullpath, '*.xml'))[0]
                                e = xml.etree.ElementTree.parse(xml_file).getroot()
                                acquisition_type = []
                                for atype in e.findall('Sequence'):
                                    acquisition_type.append(atype.get('type'))
                                if any(s=="AtlasVolume" for s in acquisition_type):
                                    atlas_volume = True

                                if not atlas_volume:
                                    convert_to_mptiff_list.append(tiff_list)

    return convert_from_raw_list, convert_to_mptiff_list


def backup(exclude_folders):
    '''
    This function is responsible for externally calling robocopy to recursively copy the new/changed data from the
    SOURCES folders to the storage server. The user name -> server path mappings are defined in the SERVER_MAPPINGS dictionary

    Robocopy options:
    /E - recursively copy all subfolders (even empty ones)
    /FFT - assume FAT File Times (2-second granularity) important for copying from Windows to Linux-based systems
    /R:1 - retry copying the same file 1 times
    /W:3 - wait 3 secs between retries
    /Z - copy in resume mode - allows aborted transfer to resume from previous point
    /MT:8 - use multiple threads (copy 8 files at a time)
    /LOG:... - write progress to log file
    /NP - disable per file percent progress reporting
    /XD - exclude list of folders (used to prevent backing up folders which have just been converted from RAW to 1000's of TIFFs)
    '''
    exclude_folders = [folder.replace('/', '\\') for folder in exclude_folders]
    for user, user_name in sorted(SERVER_MAPPINGS.items()):
        for src in SOURCES:
            source_folder = os.path.join(src, user_name)
            print(source_folder)
            dest_folder = DESTINATION.replace('*', user_name)
            if os.path.exists(source_folder):
                print('Backing up ' + colored(source_folder, 'cyan') + ' to ' + colored(dest_folder, 'yellow'))
                args = ["robocopy", source_folder, dest_folder, "/E", "/FFT", "/R:1", "/W:3", "/Z", "/MT:8", "/LOG+:"+ROBOCOPY_LOGFILE, "/NP", "/XD"]
                args.extend(exclude_folders)
                arg_string = " ".join(args)
                cmd_string_length = len(arg_string)  # may need to test if this is under 8192 characters... or it might be 32768...
                subprocess.call(args)

    # PyBehaviour results specifically. All results should go to e.g. 'lrussell' on server
    pyb_matches = [s for s in SOURCES if "PyBehaviour/Results" in s]
    if any(pyb_matches):
        source_folder = pyb_matches[0]
        dest_folder = DESTINATION.replace('*', SERVER_MAPPINGS['PyBehaviour']).replace('Data','Behaviour/Results')
        if os.path.exists(source_folder):
            print('Backing up ' + colored(source_folder, 'cyan') + ' to ' + colored(dest_folder, 'yellow'))
            args = ["robocopy", source_folder, dest_folder, "/E", "/FFT", "/R:1", "/W:3", "/Z", "/MT:8", "/LOG+:"+ROBOCOPY_LOGFILE, "/NP", "/XD"]
            args.extend(exclude_folders)
            arg_string = " ".join(args)
            cmd_string_length = len(arg_string)  # may need to test if this is under 8192 characters... or it might be 32768...
            subprocess.call(args)


def main():
    '''
    This is the main function which will sequentially:
    1. Trawl through source folders and build file listing
    2. Start the RAWDATA conversion if neccessary (this is external and asynchronous to the rest of the script)
    3. Combine single page TIFFs to MPTIFFs
    4. Then, backup to server
    '''
    
    # record start time
    t0 = time.time()

    # get complete drive listing
    convert_from_raw_list = []
    convert_to_mptiff_list = []

    print(colored('\n' + 'FILE LISTINGS', 'grey','on_white'))
    for src in SOURCES:

        [convert_raw_listing, convert_mptiff_listing] = get_listing(src)
        convert_from_raw_list.append(convert_raw_listing)
        convert_to_mptiff_list.append(convert_mptiff_listing)

    # flatten file lists
    convert_from_raw_list = [item for sublist in convert_from_raw_list for item in sublist]
    convert_to_mptiff_list = [item for sublist in convert_to_mptiff_list for item in sublist]

    e1 = time.time() - t0

    # use Image-Block ripping utility to convert RAW files
    with open(CONVERT_LOGFILE, 'a') as logfile:
        logfile.write('Convert RAW to TIFF:' + '\n')
        if DO_CONVERT_RAW:
            print(colored('\n' + 'RAWDATA FILES', 'grey','on_white'))
            if len(convert_from_raw_list) > 0:
                print('Converting RAWDATA files... (' + str(len(convert_from_raw_list)) + ' file(s))')
                logfile.write('\n'.join(convert_from_raw_list))
                convert_raw_to_tiff(convert_from_raw_list)
            else:
                print('No RAWDATA files to convert')
            e2 = time.time() - t0

    # combine single tiffs into one multipage tiff
    with open(CONVERT_LOGFILE, 'a') as logfile:
        logfile.write('\n' + '\n' + 'Combine to MPTIFF:' + '\n')
        if DO_COMBINE:
            print(colored('\n' + 'COMBINE TIFFs', 'grey','on_white'))
            if len(convert_to_mptiff_list) > 0:
                print('Combining TIFFs... (' + str(len(convert_to_mptiff_list)) + ' file(s))')
                for tiff_list in convert_to_mptiff_list:
                    convert_to_mptiff(tiff_list)
                    logfile.write(tiff_list[0] + '\n')
            else:
                print('No TIFFs to combine')
            e3 = time.time() - t0
    # transfer data to server
    if DO_BACKUP:
        print(colored('\n' + 'BACKUP', 'grey','on_white'))
        exclude_folders = convert_from_raw_list
        backup(exclude_folders)
        e4 = time.time() - t0

    e5 = time.time() - t0

    print(colored('\n' + '\n' + 'Completed in ' + '{0:.2f}'.format(e5/60) + ' minutes', 'white','on_green'))


if __name__ == '__main__':
    main()
