# TODO

1. currently structured to download a batch of files, then the uploader iterates over those files and for each one if it does not already exist in the destination, it uploads it. After the upload is done iterating, downloaded batch is removed.
   1. Lot of opportunity for optimization here. What I should do is build the tree, get the batch from the tree, don't download, check the destination to see each exists and if it does not, _then_ download and upload. That way files already in the destination don't waste download time. 

THE ABOVE IS DONE.

## Web App
- DNS. Need to finalize the name. 
- DONE. Linode, or EC2 instance 
- Twilio messaging service with callback. Ask user if they want SMS notifications for migration if admin has SMS notifications enabled.
- AWS EC2 & lambda provisioning - spin up S3 & lambda for each migration job instead of using local FS. MVP status currently. 
- Change Admin settings form to use password inputs - currently using Django’s built-in admin form. Prettify JSONfield inputs. 
- Use AAD application setting to determine user provisioning from SSO. Auto-provision = yes/no. Currently auto-provisions user if they successfully authenticate.
- Progress tracking of migration. Not sure where to house this information. Would rather not make a DB call every time a file op finishes. Already have state polling, progress may be too granular. 
- DONE. State changes - Scanning & Scan complete added to migrations list table. Listen with JS polling. Let "Scanned" be a state. Set that when scan complete
- Dockerize application. Web app, Redis, Celery worker, Database. Perhaps an additional container that proxies requests to AWS for lambda and S3 provisioning on new migration jobs. 
