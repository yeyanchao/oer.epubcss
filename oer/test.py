#from nose.tools import eq_, ok_
from lxml import etree
from epubcss import AddNumbering

def eq_(expect, actual):
  if expect != actual:
    print "ERROR!"
    print "expected=[" + expect + "]"
    print "actual  =[" + actual + "]"

def run(html, css):
  actual = AddNumbering().transform(html, [css], pretty_print = False)
  return etree.tostring(actual)

def test_content_basic():
  css    = """body { content: "pass"; }"""
  html   = """<html><body>fail</body></html>"""
  expect = """<html><body>pass</body></html>"""
  eq_(expect, run(html, css))

def test_pseudo_simple():
  css    = """body::before { content: "before"; }
              body::after { content: "after"; }
              """
  html   = """<html><body>text1<em/>text2</body></html>"""
  expect = """<html><body><span class="pseudo-before">before</span>text1<em/>text2<span class="pseudo-after">after</span></body></html>"""
  eq_(expect, run(html, css))

def test_attr():
  css    = """body:before { content: attr(href); }"""
  html   = """<html><body href="pass">fail</body></html>"""
  expect = """<html><body href="pass"><span class="pseudo-before">pass</span>fail</body></html>"""
  eq_(expect, run(html, css))

def test_counter():
  css    = """body { counter-reset: a 10 b c 20; }
              body { counter-increment: a b 2 c; }
              body { content: "a=" counter(a) ",b=" counter(b) ",c=" counter(c); }
              """
  html   = """<html><body>fail</body></html>"""
  expect = """<html><body>a=11,b=2,c=21</body></html>"""
  eq_(expect, run(html, css))

def test_target_counter():
  css    = """body        { counter-reset: counter 20; }
              em          { counter-increment: counter; }
              test        { content: target-counter(attr(href), counter); }
              test:before { content: target-counter(attr(href), counter, lower-roman); }
              test:after  { content: target-counter(attr(href), counter, upper-latin); }
              """
  html   = """<html><body><test href="#correct"/><em id="some-other-test"/><em id="correct"/></body></html>"""
  expect = """<html><body><test href="#correct"><span class="pseudo-before">xxii</span>22<span class="pseudo-after">V</span></test><em id="some-other-test"/><em id="correct"/></body></html>"""
  eq_(expect, run(html, css))

def test_content_replace_and_counter():
  """ This test replaces the content of an element (deleting the child) and increments the child"""
  css    = """test        { counter-increment: counter; }
              body        { content: target-counter(attr(href), counter); }
              body:before { content: target-counter(attr(href), counter); }
              """
  html   = """<html><body href="#correct"><test id="some-other-test"/><test id="correct"/></body></html>"""
  expect = """<html><body href="#correct"><span class="pseudo-before">2</span>2</body></html>"""
  eq_(expect, run(html, css))

def test_display_none():
  css    = """.hide       { display: none; }
              test        { counter-increment: counter; }
              test        { content: counter(counter); }
              """
  html   = """<html><body><test class="hide"/><test class="hide"/><test/></body></html>"""
  expect = """<html><body><test>1</test></body></html>"""
  eq_(expect, run(html, css))

def test_target_text():
  css    = """test          { content: target-text(attr(href), content()); }
              test::before  { content: target-text(attr(href), content(before)); }
              test::after   { content: target-text(attr(href), content(after)); }
              test2::before { content: "BEFORE"; }
              test2::after  { content: "AFTER"; }
              inner::before { content: "B"; }
              inner::after  { content: "D"; }
              hide          { display: none; }
              """
  html   = """<html><body><test href="#itsme"/><test2 id="itsme">A<inner>C<hide>XXX</hide></inner>E</test2>X</body></html>"""
  expect = """<html><body><test href="#itsme"><span class="pseudo-before">BEFORE</span>ABCDE<span class="pseudo-after">AFTER</span></test><test2 id="itsme"><span class="pseudo-before">BEFORE</span>A<inner><span class="pseudo-before">B</span>C<span class="pseudo-after">D</span></inner>E<span class="pseudo-after">AFTER</span></test2>X</body></html>"""
  eq_(expect, run(html, css))


def main():
  test_target_text()
  test_display_none()
  test_content_replace_and_counter()
  test_target_counter()
  test_content_basic()
  test_pseudo_simple()
  test_attr()

if __name__ == '__main__':
    import sys
    sys.exit(main())
