 What is this?
===============

The EPUB spec supports a subset of the CSS2 spec.
This package takes an HTML file and CSS and changes it so CSS features that aren't in the EPUB spec get "baked into" the HTML.

Some useful "features" in CSS that aren't supported:
- pseudo-elements like ::before and ::after
- counters for numbering sections, figures, tables, etc
- the content property (used to replace the contents of a tag

Specifically, this supports:
- https://developer.mozilla.org/en/CSS/%3abefore
- https://developer.mozilla.org/en/CSS/content
- https://developer.mozilla.org/en/CSS/counter
- https://developer.mozilla.org/en/CSS/counter-reset
- https://developer.mozilla.org/en/CSS/counter-increment
- http://www.w3.org/TR/css3-gcpm/#the-target-counter-and-target-counters-v

The resulting HTML file has all of these pseudo elements and replaced content "baked in".

Since the same CSS *can* be used for other output formats you should list multiple properties and this will use the last property that's parseable.

For example, let's say you have the following link.

Be sure to check out <a href="#factoring">Factoring Polynomials</a>.

and the follwing style::
  a[href] {
    content: target-counter(attr(href), chapter) "." target-counter-(attr(href), section) " " content();
    content: content() " (Page " target-counter(attr(href), page) ")"; 
  }

If you have a rendering tool that understands page numbers (like PDF) then both lines work and the 2nd one will be used resulting in something like::
  Be sure to check out Factoring Polynomails (Page 43)

Whereas this tool will only parse the 1st (it doesn't recognize the counter named "page") and result in something like::
  Be sure to check out 1.2 Factoring Polynomials


Best Practices:
* Use http://lesscss.org

