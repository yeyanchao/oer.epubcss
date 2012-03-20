==============
 What is this?
==============

The EPUB spec supports a subset of the CSS2 spec.
This package takes an HTML file and CSS3 and changes it so CSS features that aren't in the EPUB spec get "baked into" the HTML.

Some useful "features" in CSS that are "baked in" using this tool:

- pseudo-elements like ``::before`` and ``::after``
- counters for numbering sections, figures, tables, etc
- the content property (used to replace the contents of a tag)
- looking up text elsewhere (target-text)

Specifically, this supports:

- https://developer.mozilla.org/en/CSS/%3abefore
- https://developer.mozilla.org/en/CSS/content
- https://developer.mozilla.org/en/CSS/counter
- https://developer.mozilla.org/en/CSS/counter-reset
- https://developer.mozilla.org/en/CSS/counter-increment
- http://www.w3.org/TR/css3-gcpm/#the-target-counter-and-target-counters-v
- http://www.w3.org/TR/css3-gcpm/#the-target-text-value

The resulting HTML file has all of these pseudo elements and replaced content "baked in".

Since the same CSS *can* be used for other output formats you should list multiple properties and this will use the last property that's parseable.

==========
 Examples
==========

------------------------------
 Pseudo and Counters (CSS 2)
------------------------------

Let's say you want to add numbering for figures::

  figure { counter-increment: figure; }
  figure caption::before { content: "Figure " counter(figure) ": "; }

  <figure><img src=".."/><caption>Such a cute cat</caption></figure>

There are 2 features of CSS 2 that we used but EPUB does not support.
This tool takes both the CSS and HTML and transforms it into the following::

  <figure><img src=".."/><caption><span>Figure 12: </span>Such a cute cat</caption></figure>



For example, let's say you have the following link::

  Be sure to check out <a href="#factoring">Factoring Polynomials</a>.

and the follwing style::

  a[href] {
    content: target-text(attr(href), content(before)) target-text(attr(href), content());
    content: content() " (Page " target-counter(attr(href), page) ")"; 
  }

If you have a rendering tool that understands page numbers (like PDF) then both lines work and the 2nd one will be used resulting in something like::

  Be sure to check out Factoring Polynomails (Page 43)

Whereas this tool will only parse the 1st (it doesn't recognize the counter named "page") and result in something like::

  Be sure to check out <a href="#factoring">1.2 Factoring Polynomials<a>


PS: Use http://lesscss.org
