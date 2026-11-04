LWFE 0.1.2 and later create a new timestamped DIRECTORY snapshot here whenever the application starts.
Each snapshot contains the current project files, lwfe.json, and all existing sounds/*.wav files at that moment.
Older archive ZIP files from earlier LWFE versions are historical and are retained; they are not overwritten or included in new snapshots.
The archives directory is never copied into a snapshot, preventing recursive archives.
