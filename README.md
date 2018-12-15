# Minimalist Source Code Viewer for Nginx

Copyright 2018 Dries007

Based on highlightjs, highlightjs-line-numbers.

Written in about a day because I wanted to display my code pretty for for Master Thesis.

When combined with some nginx configuration, all the clever bits happen client side.

Inspired by https://stackoverflow.com/a/41532293

Feel free to use under terms of MIT license, with link back to this gist.

There is a screenshot down below!

## Make it work

+ Create an nginx include file from the two files below (paste the html into the indicated spot).
+ Host the requred files. (highlightjs with required languages supported and styles)
+ Adjust nginx & html as required. *Make sure you do not use single quotes anywhere in the HTML!*
+ Magic!
