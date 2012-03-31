"""
For all the tests you'd like to be able to diff before committing be sure to run this right after checking out this code.
That way you have a control group (what the files looked like before making changes).

Then, make some changes and re-run the tests on each (checking what the report HTML file looks like to see diffs)


Also, be sure to check out https://github.com/philschatz/oer.epubcss into the current directory (so oer is in this dir).
"""

import os
import sys
import re
from StringIO import StringIO
from lxml import etree
from epubcss import AddNumbering

VERBOSE = False # Overridden in the command line
COMPARE_XSL = etree.XSLT(etree.parse(StringIO("""

<xsl:stylesheet 
  xmlns="http://www.w3.org/1999/xhtml"
  xmlns:h="http://www.w3.org/1999/xhtml"
  xmlns:exslt="http://exslt.org/common"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">

<!-- This XSLT takes an HTML file and the path to an "old" HTML file and does a diff on them (including @class attributes) -->

<xsl:param name="cssPath" select="''" />
<xsl:param name="oldPath" select="'INVALID_VALUE._NEED_TO_SET_oldPath'" />

<xsl:template match="/">
<!--
<xsl:message>oldPath=[<xsl:value-of select="$oldPath"/>]</xsl:message>
-->
  <xsl:variable name="old" select="document($oldPath)"/>
  <xsl:choose>
    <xsl:when test="$oldPath = '' or count($old) = 0">
      <xsl:message> oldPath currently set to "<xsl:value-of select="$oldPath"/>" and csspath="<xsl:value-of select="$cssPath"/>"</xsl:message>
      <xsl:message>You must set the XSL param oldPath to point to a valid document to compare against</xsl:message>
    </xsl:when>
    <xsl:otherwise>
      <xsl:call-template name="children">
        <xsl:with-param name="old" select="$old"/>
      </xsl:call-template>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template name="children">
  <xsl:param name="old"/>
  <xsl:variable name="newCount" select="count(node())"/>
  <xsl:for-each select="node()">
    <xsl:variable name="pos" select="position()"/>
    <xsl:apply-templates select=".">
      <xsl:with-param name="old" select="$old/node()[$pos]"/>
    </xsl:apply-templates>
  </xsl:for-each>
  <xsl:if test="count($old/node()) &gt; $newCount">
    <span class="removed">
      <span class="message">[DIFF: <xsl:value-of select="count($old/node()) - $newCount"/> Nodes were removed]</span>
      <xsl:apply-templates mode="ident" select="$old/node()[position() &gt; $newCount]"/>
    </span>
  </xsl:if>
</xsl:template>

<xsl:template match="@*">
  <xsl:copy/>
</xsl:template>
<xsl:template match="node()">
  <xsl:param name="old"/>
  <xsl:copy>
    <xsl:apply-templates select="@*"/>
    <xsl:call-template name="children">
      <xsl:with-param name="old" select="$old"/>
    </xsl:call-template>
  </xsl:copy>
</xsl:template>

<xsl:template mode="ident" match="@*|node()">
  <xsl:copy>
    <xsl:apply-templates mode="ident" select="@*|node()"/>
  </xsl:copy>
</xsl:template>

<!-- Inject a style so the Report is "colorful" -->
<xsl:template match="h:head">
  <xsl:copy>
    <xsl:apply-templates mode="ident" select="node()"/>
    <xsl:choose>
      <xsl:when test="$cssPath != ''">
        <link rel="stylesheet" href="{$cssPath}"/>
      </xsl:when>
      <xsl:otherwise>
        <base href=".."/>
      </xsl:otherwise>
    </xsl:choose>
    <style>
      .mismatch { background-color: #ffffcc !important; border: 1px dashed; display: inherit; }
      .added    { background-color: #ccffcc !important; border: 1px dashed; display: inherit; }
      .removed  { background-color: #ffcccc !important; border: 1px dashed; display: inherit; }
      .mismatch * { margin-left: 2em; }
      .pseudo-before,   .pseudo-after   { color: #cccccc; }
      .pseudo-before *, .pseudo-after * { color: black; }
    </style>
  </xsl:copy>
</xsl:template>

<xsl:template match="*">
  <xsl:param name="old"/>
  <xsl:choose>
    <xsl:when test="not($old)">
      <span class="added tag">
        <span class="message">[DIFF: New element: <xsl:value-of select="name(.)"/><xsl:if test="@class"> class="<xsl:value-of select="@class"/>"</xsl:if><xsl:if test="@style"> style="<xsl:value-of select="@style"/>"</xsl:if>]</span>
        <xsl:apply-templates mode="ident" select="."/>
      </span>
    </xsl:when>
    <xsl:otherwise>
      <xsl:if test="name(.) != name($old)">
        <span class="mismatch tag">[DIFF: The tags mismatch: old="<xsl:value-of select="name($old)"/>" and new="<xsl:value-of select="name(.)"/>"]</span>
      </xsl:if>
      
      <xsl:copy>
        <xsl:apply-templates select="@*"/>
        <xsl:if test="string(./@class) != string($old/@class)">
          <span class="mismatch class">[DIFF: Classes mismatch: old="<xsl:value-of select="$old/@class"/>" and new="<xsl:value-of select="./@class"/>"]</span>
        </xsl:if>
        <xsl:if test="string(./@style) != string($old/@style)">
          <span class="mismatch style">[DIFF: Styles mismatch: old="<xsl:value-of select="$old/@style"/>" and new="<xsl:value-of select="./@style"/>"]</span>
        </xsl:if>
        <xsl:call-template name="children">
          <xsl:with-param name="old" select="$old"/>
        </xsl:call-template>
      </xsl:copy>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template match="text()">
  <xsl:param name="old"/>
  <xsl:choose>
    <xsl:when test="normalize-space(string(.)) != normalize-space(string($old))">
      <span class="mismatch text">[DIFF: Text mismatch. old="<xsl:value-of select="$old"/>"]</span>
      <xsl:copy/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:copy/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

</xsl:stylesheet>

""")))

def transform(xsl, xml, **kwargs):
  to_text = etree.XSLT(etree.fromstring(xsl))
  result = to_text(xml)
  return etree.tostring(result, **kwargs)


TRIM_WHITESPACE = re.compile(r'\s+')

# Get the HTML with styles applied
def find_styled_tags(html, css, verbose=False):
  styled = AddNumbering(verbose=verbose).transform(etree.tostring(html), css, pretty_print = False)
  return etree.tostring(styled)

def main():
  try:
    import argparse
    parser = argparse.ArgumentParser(description='This file runs a Diff on a HTML+CSS pair to understand what effect code changes have.\n Also, generates a HTML diff that is viewable in a browser.')
    parser.add_argument('-v', dest='verbose', help='Verbose printing to stderr', action='store_true')
    parser.add_argument('-r', dest='rebase', help='Make the just-generated HTML be the "Control" HTML (automatically done the 1st time you create a new test dir)', action='store_true')
    parser.add_argument('-f', dest='force', help='Force a rebase', action='store_true')
    parser.add_argument('-c', dest='css', help='CSS File', type=argparse.FileType('r'), nargs='?')
    parser.add_argument('test_dir')
    parser.add_argument('html', type=argparse.FileType('r'))
    args = parser.parse_args()

    html = etree.fromstring(args.html.read())
    # if args.verbose: print >> sys.stderr, "Transforming..."

    OLD_HTML = 'old.xhtml'
    NEW_HTML = 'new.xhtml'
    DIFF_HTML = 'report.xhtml'
    OLD_CSS = 'squirreled-away.css'
    NEW_CSS = 'style.css'
    
    old_css = os.path.join(args.test_dir, OLD_CSS)
    old_html = os.path.join(args.test_dir, OLD_HTML)
    new_css = os.path.join(args.test_dir, NEW_CSS)
    new_html = os.path.join(args.test_dir, NEW_HTML)
    diff_html = os.path.join(args.test_dir, DIFF_HTML)

    if not os.path.isdir(args.test_dir):
      os.mkdir(args.test_dir)
      args.rebase = True
      args.force = True
    if not os.path.isfile(old_html):
      args.rebase = True
      args.force = True

    css = []
    if args.css:
      css = [ args.css.read() ]
      open(new_css, 'w').write(css[0])
    
    new_html_data = find_styled_tags(html, css, verbose=args.verbose)
    open(new_html, 'w').write(new_html_data)
    
    if args.rebase:
      # Move the new files to the old
      if args.force:
        response = 'yes'
      else:
        response = raw_input("Are you sure you want to rebase? [no]: ")
      if response == 'yes':
        if os.path.isfile(new_css):
          os.rename(new_css, old_css)
        os.rename(new_html, old_html)
        print "Rebased!"
      else:
        print "Rebase Cancelled"

    # Generate the report
    if not args.rebase:
      old_html_path = "file://" + os.path.join(os.getcwd(), old_html)
      diff_html_data = COMPARE_XSL(etree.parse(StringIO(new_html_data)), cssPath="'%s'" % NEW_CSS, oldPath="'%s'" % old_html_path)
      for log in COMPARE_XSL.error_log:
        print >> sys.stderr, log.message
      diff_str = etree.tostring(diff_html_data)
      diff_file = open(diff_html, 'w')
      diff_file.write(diff_str)
      print "Generated HTML diff at %s. Check it out!" % diff_html

  except ImportError:
    print "argparse is needed for commandline"

if __name__ == '__main__':
    sys.exit(main())
