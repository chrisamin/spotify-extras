spotify-extras

Notification and media key support for qt Spotify.

Inspired by http://code.google.com/p/spotify-notify/, it has the following
improvements:

    * Persists over multiple qt Spotify instances, so you can run 
      spotify-extras at log in and then open/close Spotify as many times as
      you like.
    * Deletes obsolete notifications so cycling through tracks doesn't create
      a huge backlog.
    * Fetches default icon from spotify website.
    * Notifies on stop as well as start.
    * Won't fetch the image for every track -- only once per album.
