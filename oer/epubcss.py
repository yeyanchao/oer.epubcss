import os
import sys
import codecs
from StringIO import StringIO
from lxml import etree

from custom import premailer
from custom import numbers
from custom.util import PropertyParser, ContentPropertyParser, parse_style

__all__ = ['AddNumbering', 'UnsupportedError']

STYLE_ATTRIBUTE = '_custom_style'

PSEUDO_ELEMENT_NAME = '{http://www.w3.org/1999/xhtml}span' # For HTML5, it would be 'ins'

class UnsupportedError(Exception): pass

class State(object):
  def __init__(self, node, counters):
    self.node = node
    self.counters = counters.copy()

class AddNumbering(object):

  def __init__(self, verbose=False):
    self.counters = {}
    self.node_at = {}
    self.reprocess = [] # nodes with content: target-counter(....) and the current counter values at that point for the node: (etree.Element, {'name', 4})
    self.verbose = verbose

  def transform(self, html, explicit_styles = [], pretty_print = True):
    xpath = etree.XPath('//*')
    
    p = premailer.Premailer(html, explicit_styles=explicit_styles, remove_classes=False, custom_style_attrib=STYLE_ATTRIBUTE, verbose=self.verbose)
    html = p.transform(pretty_print=pretty_print)
    html = etree.parse(StringIO(html))
    nodes = xpath(html)
    
    # Passes:
    # - expand all pseudo nodes and remove all hidden ones
    #   - find all the targets we'll need to look up
    # - calculate all the counters and save counters that will need to be looked up (target-counter)
    # - recalculate all the remaining content (that has target-counter) by looking up the nodes
    # - remove the styling attribute
    
    if self.verbose: print >> sys.stderr, "-------- Creating pseudo elements ( CSS :before and :after ) : %d" % len(nodes)
    for node in nodes:
      style = node.attrib.get(STYLE_ATTRIBUTE, '')
      self.expand_pseudo(node, style)
    
    if self.verbose: print >> sys.stderr, "-------- Running counters and generating simple content",
    nodes = xpath(html) # we may have added pseudo nodes so re-self.update
    if self.verbose: print >> sys.stderr, ": %d" % len(nodes)
    # This has to be done in a separate pass so we can look up target-counter
    for node in nodes:
      self.mutate_node(node)

    if self.verbose: print >> sys.stderr, "-------- Resolving link counters ( CSS3 target-counter ) : %d" % len(self.reprocess)
    for (node, self.countersAt) in self.reprocess:
      self.counters = self.countersAt
      d = PropertyParser().parse(node.attrib.get(STYLE_ATTRIBUTE, ''))
      if 'content' in d:
        self._replace_content(node, d['content'])
        # also remove non-pseudo elements
        for child in node:
          if not self.is_pseudo(child):
            node.remove(child)
    
    # Clean up the HTML.
    for node in nodes:
      if STYLE_ATTRIBUTE in node.attrib:
        del node.attrib[STYLE_ATTRIBUTE]
    
    return html

  def is_pseudo(self, node):
    return node.attrib.get('class', '') in ('pseudo-before', 'pseudo-after')
  
  def _replace_content(self, node, content):
    # because of lxml's use of text tails, if we have:
    # <node><pseudo-before>...</pseudo-before>...</node>
    #
    # then if we just set node.text='foo' then we'd get:
    # <node>foo<pseudo-before>...</pseudo-before>...</node>
    #
    # instead of the expected:
    # <node><pseudo-before>...</pseudo-before>foo</node>
    #
    text = self.make_content(node, content)
    if len(node) > 0 and self.is_pseudo(node[0]):
      node[0].tail = text
    else:
      node.text = text

  def lookup_state(self, node, attr):
    id = node.attrib.get(attr, None)
    if id:
      if id[0] == '#':
        id = id[1:]
      if id in self.node_at:
        return self.node_at[id]
  
  def lookup_text(self, node, attr, which):
    """ Used by target-text(attr(href), content(first-letter)) """
    state = self.lookup_state(node, attr)
    if state:
      if which == 'before':
        if len(state.node) > 0 and self.is_pseudo(state.node[0]):
          return state.node[0].text # guaranteed it doesn;t have child elements
      elif which == 'after':
        if len(state.node) > 0 and self.is_pseudo(state.node[-1]):
          return state.node[-1].text # guaranteed it doesn;t have child elements
      else:
        text = ''
        if state.node.text: text += state.node.text
        def rec_add(n):
          text = ''
          if n.text: text += n.text
          for s in n: text += rec_add(s)
          if n.tail: text += n.tail
          return text
        for child in state.node:
          if not self.is_pseudo(child):
            text += rec_add(child)
          elif child.tail: text += child.tail
        text = ''.join(text)
        if which == 'first-letter':
          text = text.strip()
          if text: return text[0]
          else: return ''
        else: return text
    
  def lookup_counter(self, node, attr, name):
    # Look up the node (strip of the leading "#" in the href)
    v = 0
    state = self.lookup_state(node, attr)
    if state:
      if not state.counters:
        if self.verbose: print >> sys.stderr, "WARNING: Trying to get target-counter of a non-existent id '%s'" % id
      elif name in state.counters:
        v = state.counters[name]
    else:
      if self.verbose: print >> sys.stderr, "WARNING: Element %s does not have attribute '%s' to look up" % (node.tag, attr)
    return v

  def make_content(self, node, content):
    vals = [] # Accumulator
    for (function, args) in content:
      if function is None:
        vals.append(args)
      else:
        name = function
        method = '_eval_' + name.replace('-', '_')
        if not hasattr(self, method):
          raise UnsupportedError("The CSS content function %r is unsupported" % name)
        method = getattr(self, method)
        val = method(node, args)
        if val is not None: vals.append(val)

    if self.verbose: print >> sys.stderr, "DEBUG: Generated: [%s] from content:[%s]" % (''.join(vals), content)
    ret = ''.join(vals)
    return ret

  def _eval_target_text(self, node, args):
    (attr, which) = args
    n = node
    if self.is_pseudo(node):
      n = node.getparent()
    v = self.lookup_text(n, attr, which)
    return v

  def _eval_target_counter(self, node, args):
    (attr, name, numbering) = args
    n = node
    if self.is_pseudo(node):
      n = node.getparent()
    v = self.lookup_counter(n, attr, name)
    if v and name != 'page':
      # TODO: use numbering to customize how it's rendered (decimal, upper-roman, etc)
      return numbers.toString(v, numbering)

  def _eval_counter(self, node, args):
    # These look like: "counter(chapter)" or "counter(chapter, upper-roman)"
    (name, numbering) = args
    v = 0
    if name in self.counters:
      v = self.counters[name]
    if v and name != 'page':
      return numbers.toString(v, numbering)

  def _eval_attr(self, node, args):
    (name, type_, value) = args
    n = node
    if self.is_pseudo(node):
      n = node.getparent()
    v = n.attrib.get(name, '')
    return v

  def _eval_content(self, node, args):
    # TODO: Just the text may not be enough to match the spec
    assert args == ''
    return node.text

  def _eval_leader(self, node, args):
    # Ignore the leader function
    pass

  def update_counters(self, node, d):
    if 'counter-reset' in d:
      for (name, v) in d['counter-reset']:
        if name == 'none': continue
        if self.verbose: print >> sys.stderr, "Resetting %s to %d" % (name, v)
        self.counters[name] = v
    if 'counter-increment' in d:
      for (name, v) in d['counter-increment']:
        if self.verbose: print >> sys.stderr, "Incrementing %s by %s" % (name, str(v))
        if name not in self.counters:
          self.counters[name] = 0
        self.counters[name] += v

  def mutate_node(self, node):
    d = PropertyParser().parse(node.attrib.get(STYLE_ATTRIBUTE, ''))
    if d:
      self.update_counters(node, d)
    # if there's a target-counter pointing to this node, squirrel the counter (TODO: Should this be done _before_ incrementing?)
    id = node.attrib.get('id', None)
    if id and id in self.node_at:
      self.node_at[id] = State(node, self.counters)
    if d:
      # We'll have to look up the id later to find the counter
      if 'content' in d:
        has_target = False
        for (key, _) in d['content']:
          if key in [ 'target-counter', 'target-text' ]:
            has_target = True
        if has_target:
          self.reprocess.append((node, State(node, self.counters)))
        else:
          self._replace_content(node, d['content'])

  def expand_pseudo(self, node, style, class_ = ''):
    d = parse_style(style, class_)
    
    if 'display' in d and 'none' == d['display']:
      node.getparent().remove(node)
      return
      
    newStyle = _style_to_string(d)
    node.attrib[STYLE_ATTRIBUTE] = newStyle
    # Also, if there's a target-counter then add it to the list
    if 'content' in d:
      content = ContentPropertyParser().parse(d['content'])
      if content is not None:
        for (function, args) in content:
          attr = None
          if function == 'target-counter':
            (attr, _, _) = args
          if function == 'target-text':
            (attr, _) = args
          
          if attr:
            n = node
            # If it's a pseudo element use the parent's attribute
            if class_ != '': n = node.getparent()
            id = n.attrib.get(attr, '')
            if id and len(id) > 0:
              # omit the hash tag
              if id[0] == '#':
                id = id[1:]
              self.node_at[id] = None
            else:
              if self.verbose: print >> sys.stderr, "WARNING: Ignoring lookup to a non-internal id: '%s' on a %s" % (href, n.tag)
    
    if not class_ and ':before' in style:
      pseudo = etree.Element(PSEUDO_ELEMENT_NAME)
      pseudo.attrib['class'] = 'pseudo-before'
      node.insert(0, pseudo)
      if node.text:
        pseudo.tail = node.text
        node.text = ''
      self.expand_pseudo(pseudo, style, ':before')
    
    if not class_ and ':after' in style:
      pseudo = etree.Element(PSEUDO_ELEMENT_NAME)
      pseudo.attrib['class'] = 'pseudo-after'
      node.append(pseudo)
      self.expand_pseudo(pseudo, style, ':after')


def _style_to_string(style):
  s = []
  for k, v in style.items():
    s += k + ':' + v + ';'
  return ''.join(s)



def main():
    try:
      import argparse
      parser = argparse.ArgumentParser(description='Apply CSS pseudo elements :before/:after and counters to HTML since epub does not support them')
      parser.add_argument('-v', dest='verbose', help='Verbose printing to stderr', action='store_true')
      parser.add_argument('-c', dest='css', help='CSS File', type=argparse.FileType('r'), nargs='*')
      parser.add_argument('-o', dest='output', nargs='?', type=argparse.FileType('w'), default=sys.stdout)
      parser.add_argument('html',              nargs='?', type=argparse.FileType('r'), default=sys.stdin)
      args = parser.parse_args()
  
      # if self.verbose: if self.verbose: print >> sys.stderr, "Transforming..."
      css = []
      for style in args.css:
        css.append(style.read())
      result = AddNumbering(verbose=args.verbose).transform(args.html.read(), css)
      html = etree.tostring(result, encoding='ascii')
      args.output.write(html)
      
    except ImportError:
      print "argparse is needed for commandline"

if __name__ == '__main__':
    sys.exit(main())
