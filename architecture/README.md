# Planning a Cloud Architecture for Go365 Migrator

OAuth/OIDC-based web application that allows functional users within an organization to enqueue their own data migrations from Google Drive to SharePoint Online or OneDrive for Business. Google Takeout does not offer these services.

A given user signs into the app with single-sign-on (via Azure AD, an identity provider) and authorizes the application to read/write their own data in SharePoint and OneDrive. They also sign into Google and authorize the app to read (not write) their Google data. Both of these authentication and authorization processes utilize OIDC-conforming OAuth 2.0 flows. The user then selects a source in Google they want to migrate (a folder or a shared drive), and a destination in either SharePoint Online or their OneDrive for Business account. If the destination is in SharePoint Online, they need to specify 1) a site to which they have edit access, 2) a document library (or a _drive_, which is how the Graph API refers to document libraries) on that site to which they have edit access, and 3) a folder in that document library to which they have edit access.

After they confirm their choices, the app runs an initial asynchronous scan of the data to be migrated to offer some key initial insights about data that can and cannot be migrated. The goal is to have that scan run asynchronously as a serverless function with AWS Lambda, which then posts the scan results back to the web app (running a REST API with Django REST framework) which then saves the result back to the migration object in the database.

The user, who can monitor the status of the scan from the front end of the app, views the scan results once they are ready. They can then start the migration from the scan results page.

Ideally, the migration job would similarly run asynchronously as a serverless AWS Lambda function; this function would spins up its own S3 bucket, download the Google source data in batches into that bucket, and upload those batches into the specified SPO or OneDrive for Business destination.

Once the migration job completes, the serverless function posts the migration job results back to the web app (again, running a REST API with Django REST Framework).

The web app then (optionally, up to the admin) sends notifications to the user via email and/or SMS (using a Twilio messaging service) about the completion of the migration job.

A visual architecture diagram can be found in [Go365-Migrator-Architecture.pdf](Go365-Migrator-Architecture.pdf). This diagram was put together using Visio.
