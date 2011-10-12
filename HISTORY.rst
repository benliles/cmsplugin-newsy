0.3 (2011/10/12)
----------------

* Switched to using the class based generic list view properly
* Added tag browsing support
* Added default pagination on list views of 30 (when using shortcut views)
* Added some new methods to the NewsItem model to make a few things easier
* Method for getting tag and date filters in generic view
* Added ampersands to allowed tag characters (urls.py)
* Reorganized form fields and increased the size of the title fields and tag field
* News item slugs must be lowercase
* Added the 0003 data migration to lowercase existing slugs
* Added get_next_published and get_previous_published methods to news item
* Added RSS feed for all published and for all tags (one feed per tag)

0.2 (2011/07/25)
----------------

* Added an archive view (GitHub issue #10)
* Added tags field to NewsItem model for admin integration (GitHub issue #7)
* Added tags field to NewsItem administration (GitHub issue #7)
* Added south migration for the tags field (GitHub issue #7)
* Added a news_plugins_media tag for rendering plugin media links (GitHub issue #8)
* Added a site_objects model manager to news item (GitHub issue #11)
* Modified list views to use the site_objects model manager (GitHub issue #11)
* Added permission wrapper around list view and news item view for unpublished 
  items (GitHub issue #12)

0.1 (2011/07/15)
----------------

* A very basic, working version for demonstration