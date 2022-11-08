# TODO 

1. currently structured to download a batch of files, then the uploader iterates over those files and for each one if it does not already exist in the destination, it uploads it. After the upload is done iterating, downloaded batch is removed. 
   1. Lot of opportunity for optimization here. What I should do is build the tree, get the batch from the tree, don't download, check the destination to see each exists and if it does not, *then* download and upload. That way files already in the destination don't waste download time. 