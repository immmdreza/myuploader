# Fat ass uploader
This repo contains simple Github Actions to upload files by link to your Google Drive.

## About

Github action works as a relay to access a link you can't normally access due to your fat ass! (I mean restrictions). Downloads your file and uploads it into your Google drive. We assume reaching google drive is by far easier.
Then you can download files you've uploaded from your Google Drive (GithubUploads) folder.

There're 3 actions available (All triggered manually):

- Download single file by link.
- Download multiple files by links.
- Cleanup drive folder (GithubUploads).

## Setup

You will need rclone (specially `RCLONE_CONFING` to put in repo secrets). Download `rclone`, run it and create new remote.

For windows:

```cmd
./rclone.exe config
```

Name your remote `remote` and type to `drive`. Continue by default options to the end and authenticating with google drive. then go find your config and paste the content as value for `RCLONE_CONFING`.

something like:

```toml
[remote]
name = "remote"
type = "drive"
access_token = {...}
```

And you're ready to go.

## Considerations

- Delete your workflow runs or links will be exposed.
- Action will give you direct download links just look closer after upload logs.

_Have fun 🍕_
