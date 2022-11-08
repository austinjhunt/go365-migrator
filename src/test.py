def main():
    from concurrent.futures import ThreadPoolExecutor,wait 
    def work2(a): 
        return a + 1
    def work(a): 
        mylist = []
        if a % 2 == 0: 
            with ThreadPoolExecutor(max_workers=3) as executor: 
                futures = [executor.submit(work, i) for i in range(a) if i % 2 != 0]
                waited = wait(futures)
                done = waited.done 
                assert a // 2 == len(done) 
                for f in done:
                    mylist.append(f.result()) 
        else:
            mylist.append(a)
        return mylist  

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(100):
            futures.append(executor.submit(work, i))
        waited = wait(futures) 
        print(f'Completed futures = {len(waited.done)}')      
        for future in waited.done:
            print(future.result())
        
def main2():
    import os

    # Path where we have to count files and directories
    HOME_FOLDER = 'C:\\Users\\huntaj\\OneDrive - College of Charleston\\dev\\GoogleDriveToSharePointMigrator\\Google2SharePointMigrationAssistant\\app'

    noOfFiles = 0
    noOfDir = 0

    for base, dirs, files in os.walk(HOME_FOLDER):
        print('Looking in : ',base)
        for directories in dirs:
            noOfDir += 1
        for Files in files:
            noOfFiles += 1

    print('Number of files',noOfFiles)
    print('Number of Directories',noOfDir)
    print('Total:',(noOfDir + noOfFiles))


FBS = 10 
def get_batch_for_download(trees: list = [], batch : list = []):  
    for t in trees:
        for fi in t['children_files']: 
            if len(batch) < FBS:
                batch.append(fi)
                t['children_files'].remove(fi)
            else: 
                return batch 
        if len(t['children_folders']) > 0: 
            batch = get_batch_for_download(trees=t['children_folders'], batch=batch)
    return batch 


file_batch_size = 4
def get_batch_for_download_from_files_list(files_list: list = []):   
        batch = []
        print(f'getting batch for download from files list of length {len(files_list)}')
        for file in files_list: 
            if len(batch) < file_batch_size:
                batch.append(file)
                print(f'batch before remove: {batch}')
                files_list.remove(file)
                print(f'batch after remove: {batch}')
            else: 
                return batch   
        print(f'returning batch: {batch}')
        return batch   

flist = [1,2,3,4,5,6,7,8,9,10]
resp = get_batch_for_download_from_files_list(flist)

trees = [
    {
        'children_files': ['a','b','c','d','e'],
        'children_folders': [
            {
                'children_files': ['f','g','h','i','j'],
                'children_folders': [
                    {
                    'children_files': ['k','l','m','n'],
                    'children_folders': []
                }
                    
                ]
            },
            {
                'children_files': ['ff','gg','hh','ii','jj'],
                'children_folders': [
                    {
                    'children_files': ['kk','ll','mm'],
                    'children_folders': [
                        
                    ]
                }
                    
                ]
            }
        ]
    }
]

def main3():
    from concurrent.futures import ThreadPoolExecutor,wait 
    def work(a): 
        return a + 1 

    with ThreadPoolExecutor(max_workers=3) as executor:
        nums = list(range(10))
        print(nums)
        for response in executor.map(work, nums):
            print(f'{response}')

total = 0
required = 22
while total < required: 
    batch = get_batch_for_download(trees=trees, batch=[])
    total += len(batch) 
    print(f'batch length = {len(batch)}; batch = {batch}; total = {total}; new trees = {trees}')