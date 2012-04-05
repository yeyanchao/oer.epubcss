import os
import sys
import codecs
from StringIO import StringIO
from lxml import etree

from custom import premailer
from custom import numbers
from custom.util import PropertyParser, ContentPropertyParser, parse_style, ContentEvaluator, State

__all__ = ['AddNumbering', 'UnsupportedError']

STYLE_ATTRIBUTE = '_custom_style'

class UnsupportedError(Exception): pass

class AddNumbering(object):

  def __init__(self, pseudo_element_name='{http://www.w3.org/1999/xhtml}span', verbose=False):
    self.node_at = {}
    self.evaluator = ContentEvaluator(self.node_at)
    self.reprocess = [] # nodes with content: target-counter(....) and the current counter values at that point for the node: (etree.Element, {'name', 4})
    self.verbose = verbose
    self.pseudo_element_name = pseudo_element_name


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
    for (node, self.evaluator.state.countersAt) in self.reprocess:
      self.evaluator.state.counters = self.evaluator.state.countersAt
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
    text = self.evaluator.eval_content(node, content)
    if len(node) > 0 and self.is_pseudo(node[0]):
      node[0].tail = text
    else:
      node.text = text

  def update_counters(self, node, d):
    if 'counter-reset' in d:
      for (name, v) in d['counter-reset']:
        if name == 'none': continue
        if self.verbose: print >> sys.stderr, "Resetting %s to %d" % (name, v)
        self.evaluator.state.counters[name] = v
    if 'counter-increment' in d:
      for (name, v) in d['counter-increment']:
        if self.verbose: print >> sys.stderr, "Incrementing %s by %s" % (name, str(v))
        if name not in self.evaluator.state.counters:
          self.evaluator.state.counters[name] = 0
        self.evaluator.state.counters[name] += v

  def mutate_node(self, node):
    d = PropertyParser().parse(node.attrib.get(STYLE_ATTRIBUTE, ''))
    if d:
      self.update_counters(node, d)
    # if there's a target-counter pointing to this node, squirrel the counter (TODO: Should this be done _before_ incrementing?)
    id = node.attrib.get('id', None)
    if id and id in self.node_at:
      self.node_at[id] = State(node, self.evaluator.state)
    if d:
      # We'll have to look up the id later to find the counter
      if 'content' in d:
        has_target = False
        for (key, _) in d['content']:
          if key in [ 'target-counter', 'target-text' ]:
            has_target = True
        if has_target:
          self.reprocess.append((node, State(node, self.evaluator.state)))
        else:
          self._replace_content(node, d['content'])
      # http://www.w3.org/TR/css3-gcpm/#setting-named-strings-the-string-set-pro
      if 'string-set' in d:
        has_target = False
        for (key, _) in d['string-set'][1]: # [1] because we don't want to look at the string name
          if key in [ 'target-counter', 'target-text' ]:
            has_target = True
        if has_target:
          self.reprocess.append((node, State(node, self.evaluator.state)))
        else:
          string_name = d['string-set'][0]
          string_value = d['string-set'][1]
          string_computed = self.evaluator.eval_content(node, string_value)
          # Note: The 1st "value" is actually the string name
          print "Setting string %s to [%s]" % (string_name, string_computed)
          self.evaluator.state.strings[string_name] = string_computed

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
      pseudo = etree.Element(self.pseudo_element_name)
      pseudo.attrib['class'] = 'pseudo-before'
      node.insert(0, pseudo)
      if node.text:
        pseudo.tail = node.text
        node.text = ''
      self.expand_pseudo(pseudo, style, ':before')
    
    if not class_ and ':after' in style:
      pseudo = etree.Element(self.pseudo_element_name)
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
