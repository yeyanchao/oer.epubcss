import cssselect # The customized one
from lxml.cssselect import TokenStream, String, Symbol, Token

def parse_style(style, class_ = ''):
  news = {}
  if class_:
    test = class_ + '{'
    style = style[style.find(test) + len(test):].split('}')[0]
  elif not style or style[0] == ':':
    return news
  elif style[0] == '{':
    style = style[1:style.find('}')]
  for k, v in [x.strip().split(':', 1) for x in style.split(';') if x.strip()]:
    news[k.strip()] = v.strip()
  # TODO: validate whether properties should be discarded (using ContentPropertyParser)
  return news

class PropertyParser(object):
  """ Parses all the style properties we care about (display:none, counter-reset:, counter-increment:, and content:) """
  def parse(self, style, class_ = ''):
    style = parse_style(style, class_)
    ret = {}
    for (name, value) in style.iteritems():
      method = '_parse_' + name.replace('-', '_')
      if hasattr(self, method):
        method = getattr(self, method)
        val = method(value)
        #if name in ret:
          # Decide whether to overwrite it.
          # 2 cases:
          # - doesn't have an unknown
          # - ends-with "!important"
        if val is not None:
          ret[name] = val
    return ret
  def _counter(self, value, default):
    acc = []
    stream = TokenStream(cssselect.tokenize(value))
    while stream.peek() is not None:
      name = str(stream.next())
      by = default
      if _is_int(str(stream.peek())):
        by = int(str(stream.next()))
      acc.append((name, by))
    return acc
  def _parse_counter_reset(self, value):
    return self._counter(value, 0)
  def _parse_counter_increment(self, value):
    return self._counter(value, 1)
  def _parse_content(self, value):
    return ContentPropertyParser().parse(value)
  def _parse_display(self, value):
    if 'none' in value:
      return 'none'
      

class ContentPropertyParser(object):
  
  def parse(self, content):
    """ Given a string like "'Exercise ' target-counter(attr(href, url), chapter, decimal) counters(section)"
        return a list of the form:
        (function-name or None, values) """
    vals = []
    stream = TokenStream(cssselect.tokenize(content))
    while stream.peek() is not None:
      t = stream.next()
      if isinstance(t, String):
        vals.append((None, str(t)))
      else:
        name = str(t)
        val = None
        method = '_parse_' + name.replace('-', '_')
        if hasattr(self, method):
          method = getattr(self, method)
          val = method(stream)
        #else:
        #  name = ContentPropertyParser.UNKNOWN
        #  val = [t].concat(self._unknown(stream))
        # If anything fails parsing (ie it's None) then the whole line is unusable
        if val is None:
          return None
        vals.append((name, val))
    return vals

  def _unknown(self, stream):
    # parse up to the matching close paren
    acc = []
    assert str(stream.read()) == '('
    while stream.peek() is not None and str(stream.peek()) != ')':
      if str(stream.peek()) == '(':
        acc.concat(_unknown(stream))
      else:
        acc.append(stream.read())
    return acc
      
  def _optional(self, stream, default=None):
    """ Parses an optional argument (not the 1st argument to a function) by consuming the comma """
    if str(stream.peek()) == ',':
      assert str(stream.next()) == ','
      return str(stream.next())
    return default

  def _parse_target_text(self, stream):
    # These look like: "target-counter(attr(href), counter-name)"
    #               or "target-counter(attr(href, url), counter-name)"
    #               or "target-counter(attr(href, url), counter-name, upper-roman)"
    #
    assert str(stream.next()) == '('             # ignore the outer "("
    assert str(stream.next()) == 'attr'
    (attr, _, _) = self._parse_attr(stream)
    which = 'before'                             # If there's no content(...) then before is default
    content = self._optional(stream, None)
    if content == 'content':                     # If there's a content() then all text is used
      which = 'at'
      assert str(stream.next()) == '('
      if str(stream.peek()) != ')':
        which = str(stream.next())
      assert str(stream.next()) == ')'
    assert str(stream.next()) == ')'             # ignore the outer ")"
    return (attr, which)

  def _parse_target_counter(self, stream):
    # These look like: "target-counter(attr(href), counter-name)"
    #               or "target-counter(attr(href, url), counter-name)"
    #               or "target-counter(attr(href, url), counter-name, upper-roman)"
    #
    assert str(stream.next()) == '('             # ignore the outer "("
    assert str(stream.next()) == 'attr'
    (attr, _, _) = self._parse_attr(stream)
    assert str(stream.next()) == ','             # ignore the comma
    name = str(stream.next())
    numbering = self._optional(stream, 'decimal')
    assert str(stream.next()) == ')'             # ignore the outer ")"
    if name == 'page':
      return None
    return (attr, name, numbering)

  def _parse_counter(self, stream):
    # These look like: "counter(chapter)" or "counter(chapter, upper-roman)"
    assert str(stream.next()) == '('      # ignore the "("
    name = str(stream.next())
    numbering = self._optional(stream, 'decimal')
    assert str(stream.next()) == ')'
    return (name, numbering)

  def _parse_attr(self, stream):
    assert str(stream.next()) == '('
    attr = str(stream.next())
    type_ = self._optional(stream)
    value = self._optional(stream)
    assert str(stream.next()) == ')'
    return (attr, type_, value)

  def _parse_content(self, stream):
    assert str(stream.next()) == '('
    assert str(stream.next()) == ')'
    return ''

  #def _parse_leader(self, stream):
  #  assert str(stream.next()) == '('
  #  token = stream.next()
  #  leader = ' '
  #  if isinstance(token, Token):
  #    if 'dotted' == token:
  #      leader = '. '
  #    elif 'solid' == token:
  #      leader = '_'
  #    elif 'space' == token:
  #      leader = ' '
  #  elif isinstance(token, String):
  #    leader = str(token)
  #  assert str(stream.next()) == ')'
  #  return leader


def _is_int(s):
  try: 
    int(s)
    return True
  except ValueError:
    return False
