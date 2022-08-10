import os, shutil, tarfile, time
import xml.etree.ElementTree as ET


# Names of backups; leave off .mbz suffix.
campus = "campus"
houghton = "houghton"
out_folder = "out"

# Copy backups renamed with .tgz extension.
print('Creating .tgz copies of archives')
shutil.copyfile(campus+".mbz",campus+".tgz")
shutil.copyfile(houghton+".mbz",houghton+".tgz")

# Delete any previous folders used for unpacking/building archives.
# Makes sure shutil completes before making folders.
print('Removing prior unpacked archives')
while os.path.isdir(campus) or os.path.isdir(houghton) or os.path.isdir(out_folder):

    for folder in [campus, houghton, out_folder]:
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass
        except Exception as e: 
            print(e)
            break

    time.sleep(.1)


# Make folders for unpacking/building archives.
print('Creating new folders')
os.mkdir(campus)
os.mkdir(houghton)
os.mkdir(out_folder)

# Extract campus archive into campus folder.
print('Unpacking ' + campus + '.tgz')
campus_tar = tarfile.open(campus+".tgz")
for item in campus_tar:
    campus_tar.extract(item.name,"./" + campus)
    if not (item.name == 'users.xml'):
        campus_tar.extract(item.name,"./" + out_folder)

# Extract houghton archive into houghton folder and out_folder folder.
print('Unpacking ' + houghton + '.tgz')
houghton_tar = tarfile.open(houghton+".tgz")
for item in houghton_tar:
    houghton_tar.extract(item.name,"./" + houghton)
    houghton_tar.extract(item.name,"./" + out_folder)

# The above extraction makes files from both archives present in the file system.
# When there is are two files with the same name, the houghton archive version is used.
# The file structure of a Moodle archive is stored in files.xml. We merge files.xml
# in both archives for the out_folder archive.

print('Parsing files.xml in archives')
campus_files_tree = ET.parse(campus + '/files.xml')
houghton_files_tree = ET.parse(houghton + '/files.xml')

campus_files_root = campus_files_tree.getroot()
houghton_files_root = houghton_files_tree.getroot()

print('Merging files.xml')
campus_files_root.extend(houghton_files_root)
campus_files_tree.write(out_folder + '/files.xml',encoding='utf8', method='xml')

# Moodle require UTF-8 encoding, not utf8. It will error with this alternate spelling.
f = open(out_folder + '/files.xml','r')
lines = f.readlines()
lines[0] = '<?xml version="1.0" encoding="UTF-8"?>\n'
f.close()

f = open(out_folder + '/files.xml','w')
for x in lines:
    f.writelines(x)
f.close()

# Now we create a merged version of moodle_backup.xml
print('Parsing moodle_backup.xml in archives')
campus_backup_tree = ET.parse(campus + '/moodle_backup.xml')
houghton_backup_tree = ET.parse(houghton + '/moodle_backup.xml')

campus_backup_root = campus_backup_tree.getroot()
houghton_backup_root = houghton_backup_tree.getroot()

print('Merging moodle_backup.xml')
campus_activities = campus_backup_root.find("./information/contents/activities")
for item in reversed(campus_activities):
    houghton_backup_root.find("./information/contents/activities").insert(0,item)

campus_sections = campus_backup_root.find("./information/contents/sections")
for item in reversed(campus_sections):
    houghton_backup_root.find("./information/contents/sections").insert(0,item)

campus_settings = campus_backup_root.find("./information/settings")
for item in reversed(campus_settings):
    if item.find('level').text != 'root':
        houghton_backup_root.find("./information/settings").extend(item)

houghton_backup_tree.write(out_folder + '/moodle_backup.xml',encoding='utf8', method='xml')

# Again, Moodle require UTF-8 encoding, not utf8. It will error with this alternate spelling.
f = open(out_folder + '/moodle_backup.xml','r')
lines = f.readlines()
lines[0] = '<?xml version="1.0" encoding="UTF-8"?>\n'
f.close()

# The context_id in moodle_backup.xml needs to take on the value used by campus.
# I have hard coded this in here.
f = open(out_folder + '/moodle_backup.xml','w')
for x in lines:
    if x.find('<original_course_contextid>434380</original_course_contextid>') != -1:
        f.writelines('\t<original_course_contextid>2017</original_course_contextid>\n')
    elif x.find('<original_course_format>weeks</original_course_format>') != -1:
        f.writelines('\t<original_course_format>tiles</original_course_format>\n')
    else:
        f.writelines(x)
f.close()

# Create .ARCHIVE_INDEX
campus_index = open(campus + "/.ARCHIVE_INDEX")
campus_files = [x for x in campus_index]
campus_files = campus_files[1:]
campus_filenames = [x.split('\t')[0] for x in campus_files]

houghton_index = open(houghton + "/.ARCHIVE_INDEX")
houghton_files = [x for x in houghton_index]
houghton_files = houghton_files[1:]
houghton_filenames = [x.split('\t')[0] for x in houghton_files]

for i in range(len(campus_filenames)):
    if not campus_filenames[i] in houghton_filenames:
        houghton_files.append(campus_files[i])

out_index = open(out_folder + "/.ARCHIVE_INDEX",'w')
out_index.write('Moodle archive file index. Count: ' + str(len(houghton_files)) + '\n')

for x in sorted(houghton_files):
    out_index.write(x)

out_index.close()

# In out_folder/sections/ we have section_#### folders. Within each folder is section.xml.
# In each file, there is a tag called number. Since we merged courses together, we need
# to reindex these numbers otherwise the sections will merge together when displayed.
section_dirs = os.listdir(out_folder + '/sections/')
section_dirs.sort()
section_dirs.sort(key=len)
index = 0

for x in section_dirs:
    f = open(out_folder + '/sections/' + x + '/section.xml', 'r')
    lines = f.readlines()
    f.close()
    
    f = open(out_folder + '/sections/' + x +  '/section.xml', 'w')
    for y in lines:
        if y.find('<number>') != -1:
            f.writelines('\t<number>' + str(index) + '</number>\n')
            index = index + 1
        else:
            f.writelines(y)
    f.close()

# Creating an archive
print('Archiving output')
# Moodle requires a the USTAR_FORMAT; this requirement is buried somewhere in Moodle's source code.
out_tar = tarfile.open(out_folder + ".tar.gz", "w:gz", format=tarfile.USTAR_FORMAT)
out_tar.add(out_folder, arcname = os.path.sep)
out_tar.close()

print('Creating .mbz copy of archive.')
shutil.copyfile(out_folder+".tar.gz",out_folder+".mbz")
