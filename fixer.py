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
bad_files = ['users.xml', 'badges.xml'] # We don't want these files extracted.
campus_tar = tarfile.open(campus+".tgz")
for item in campus_tar:
    campus_tar.extract(item.name,"./" + campus)
    # These files are included in the campus archive but don't appear in Houghton archives.
    # Because of that, I exclude them.
    if not (item.name in bad_files):
        campus_tar.extract(item.name,"./" + out_folder)

# Extract houghton archive into houghton folder and out_folder folder.
print('Unpacking ' + houghton + '.tgz')
houghton_tar = tarfile.open(houghton+".tgz")
for item in houghton_tar:
    houghton_tar.extract(item.name,"./" + houghton)
    if not 'course/blocks/' in item.name:
        houghton_tar.extract(item.name,"./" + out_folder)

# Below is a helper function that I will need for annoying technical issue.
# Moodle require UTF-8 encoding, not utf8. It will error with this alternate spelling.
def moodle_utf(file_name):
    f = open(file_name,'r')
    lines = f.readlines()
    lines[0] = '<?xml version="1.0" encoding="UTF-8"?>\n'
    f.close()

    f = open(file_name,'w')
    for x in lines:
        f.writelines(x)
    f.close()

# The above extraction makes files from both archives present in the file system.
# When there is are two files with the same name, the houghton archive version is used.
# The structure of a Moodle archive is stored in moodle_backup.xml. We merge moodle_backup.xml
# in both archives for the out_folder archive.
print('Parsing moodle_backup.xml in archives')
campus_backup_tree = ET.parse(campus + '/moodle_backup.xml')
houghton_backup_tree = ET.parse(houghton + '/moodle_backup.xml')

# We will need these values later!
campus_context_id = campus_backup_tree.find('./information/original_course_contextid').text
houghton_context_id = houghton_backup_tree.find('./information/original_course_contextid').text

# Continuing with merging of moodle_backup.xml
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

# We need to update the format field in the merged moodle_backup.xml
houghton_backup_tree.find("./information/original_course_format").text = "tiles"

# Now we write the merged moodle_backup.xml
houghton_backup_tree.write(out_folder + '/moodle_backup.xml',encoding='utf8', method='xml')
moodle_utf(out_folder + '/moodle_backup.xml')

# Now we create a merged version of files.xml which contains the file structure for
# a Moodle archive.
print('Parsing files.xml in archives')
campus_files_tree = ET.parse(campus + '/files.xml')
houghton_files_tree = ET.parse(houghton + '/files.xml')

campus_files_root = campus_files_tree.getroot()
houghton_files_root = houghton_files_tree.getroot()

print('Merging files.xml')
campus_files_root.extend(houghton_files_root)
campus_files_tree.write(out_folder + '/files.xml',encoding='utf8', method='xml')
moodle_utf(out_folder + '/files.xml')

# We need to update the context_ids in files.xml so that they are all the houghton_context_id.
f = open(out_folder + '/files.xml','r')
lines = f.readlines()
for i in range(len(lines)):
    lines[i] = lines[i].replace('<contextid>' + campus_context_id + '</contextid>', 
                  '<contextid>' + houghton_context_id + '</contextid>')
f.close()

f = open(out_folder + '/files.xml','w')
for x in lines:
    f.writelines(x)
f.close()

# Create .ARCHIVE_INDEX; I'm not sure if this is needed.
campus_index = open(campus + "/.ARCHIVE_INDEX")
campus_files = [x for x in campus_index]
campus_files = campus_files[1:]
campus_filenames = [x.split('\t')[0] for x in campus_files]

houghton_index = open(houghton + "/.ARCHIVE_INDEX")
houghton_files = [x for x in houghton_index]
houghton_files = houghton_files[1:]
houghton_filenames = [x.split('\t')[0] for x in houghton_files]

for i in range(len(campus_filenames)):
    #Include files from campus that are not in Houghton
    if not campus_filenames[i] in houghton_filenames:
        # Unless they are bad_files.
        if not (campus_filenames[i] in bad_files and (not'/' in campus_filenames[i])):
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

# Some items brought in by campus need to have the relevant context ids updated to that
# of the Houghton course. Specifically, each folder in blocks/ contains a block.xml.
# In these files, we need to update the tag parentcontextid to houghton_context_id.
block_dirs = os.listdir(out_folder + '/course/blocks/')

for x in block_dirs:
    f = open(out_folder + '/course/blocks/' + x + '/block.xml','r')
    lines = f.readlines()
    for i in range(len(lines)):
        lines[i] = lines[i].replace('<parentcontextid>' + campus_context_id + '</parentcontextid>', 
                  '<parentcontextid>' + houghton_context_id + '</parentcontextid>')
    f.close()
    
    f = open(out_folder + '/course/blocks/' + x + '/block.xml','w')
    for x in lines:
        f.writelines(x)
    f.close()

# The course format needs to be changes to tiles. We do that here.
f = open(out_folder + '/course/course.xml','r')
lines = f.readlines()
for i in range(len(lines)):
    if '<format>' in lines[i]:
        lines[i] = '\t<format>tiles</format>\n'
f.close()

f = open(out_folder + '/course/course.xml','w')
for x in lines:
    f.writelines(x)
f.close()


# Creating an archive
print('Archiving output')
# Moodle requires a the USTAR_FORMAT; this requirement is buried somewhere in Moodle's source code.
out_tar = tarfile.open(out_folder + ".tar.gz", "w:gz", format=tarfile.USTAR_FORMAT)
out_tar.add(out_folder, arcname = os.path.sep)
out_tar.close()

print('Creating .mbz copy of archive.')
shutil.copyfile(out_folder+".tar.gz",out_folder+".mbz")
