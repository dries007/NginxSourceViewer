#!/bin/env python3

"""
NginxSourceViewer config generator

Copyright 2018-2019 Dries007
For more info, see README.md
Hosted on https://github.com/dries007/NginxSourceViewer
"""
import json
import string
from typing import Dict, Iterable, Optional
import requests
import logging
import htmlmin


def main():
    """
    Main function. Edit configuration here if desired.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s %(levelname)s] %(message)s', datefmt='%H:%M:%S')
    logging.info('NginxSourceViewer Config Generator')

    # See https://highlightjs.org for more info on the supported languages & styles
    # The program also outputs a list later on.

    # Languages where the code is the same as the extension
    wanted_languages = {
        ext: r'\.(%s)$' % ext for ext in ('tcl', 'sql', 'gradle', 'groovy', 'java', 'lua', 'properties', 'scala')
    }
    # Special cases
    wanted_languages.update(
        python=r'\.(py)$',
        cpp=r'\.(c|cpp|h|hpp)$',
        vhdl=r'\.(vhdl?)$',
        bash=r'\.(sh)$',
        makefile=r'\.?(make|makefile)$',
        markdown=r'\.(md|markdown)$',
        sql=r'\.(sql)$',
        dos=r'\.(bat)$',
        gcode=r'\.(g|gcode)$',
        verilog=r'\.(v|verilog)$',
        kotlin=r'\.(kt)$',
        matlab=r'\.(m)$',
        openscad=r'\.(scad)$',
        powershell=r'\.(ps)$',
        tex=r'\.(latex|tex)$',
        dockerfile=r'\.?(dockerfile)$',
    )
    wanted_styles = ('idea', 'dracula', 'a11y-light', 'a11y-dark', 'github', 'github-gist', 'default', 'dark', 'xt256',
                     'solarized-light', 'solarized-dark', 'qtcreator_light', 'qtcreator_dark', 'paraiso-light', 'paraiso-dark')
    with open('highlight.conf', 'w') as f:
        f.write(run(wanted_languages, wanted_styles))


def run(languages, styles=None) -> str:
    """
    :param languages: A dictionary with language-key -> nginx regex value
    :param styles: A list of styles, or None for all.
    :return A complete Nginx config segment. Use inside a server block or an include file.

    :type languages: Dict[str, str]
    :type styles: Optional[Iterable[str]]
    :rtype str
    """
    jquery_version, jquery_files = get_cdn_files('jquery')
    highlight_version, highlight_files = get_cdn_files('highlight.js')
    line_numbers_version, line_numbers_files = get_cdn_files('highlightjs-line-numbers.js')

    logging.info('jquery v%s: %r', jquery_version, jquery_files)
    logging.info('highlight v%s: %r', highlight_version, highlight_files)
    logging.info('line_numbers v%s: %r', line_numbers_version, line_numbers_files)

    # Cut off 'languages/' and '.min.js'
    possible_languages = {x[10:-7] for x in highlight_files if x.startswith('languages/')}
    # Cut off 'style/' and '.min.css'
    possible_styles = {x[7:-8] for x in highlight_files if x.startswith('styles/')}

    logging.info('Possible languages: %r', possible_languages)
    logging.info('Possible styles: %r', possible_styles)

    if styles is None:
        styles = [*sorted(possible_styles)]
        styles.remove('default')
        styles.insert(0, 'default')

    missing_languages = set(languages.keys()) - possible_languages
    missing_styles = set(styles) - possible_styles

    if missing_languages:
        logging.warning('!!! Missing languages: %r', missing_languages)
    if missing_styles:
        logging.warning('!!! Missing styles: %r', missing_styles)

    scripts = [
        ('jquery', jquery_version, 'jquery.min.js'),
        ('highlight.js', highlight_version, 'highlight.min.js'),
        ('highlightjs-line-numbers.js', line_numbers_version, 'highlightjs-line-numbers.min.js'),
    ]

    logging.info('Creating the HTML...')
    template = string.Template(MAGIC_HTML)
    html = template.substitute(
        css=MINIFIED_CSS,
        js=MINIFIED_JS,
        styles=json.dumps(styles, separators=(',', ':')),
        scripts='\n    '.join(create_script_tag(lib, v, file) for lib, v, file in scripts),
        highlight_version=highlight_version,
    )
    # logging.info('HTML output: \n%s', html)

    if '\'' in html:
        raise ValueError('Single quotes in the HTML. This is a problem!')

    # todo: Ideally add a check here for any $ that is not $uri or $url...

    old_size = len(html)
    html = htmlmin.minify(html, remove_comments=True, remove_empty_space=True, reduce_boolean_attributes=True, remove_optional_attribute_quotes=True)
    new_size = len(html)
    logging.info('Minified HTML: %d -> %d', old_size, new_size)
    if new_size > 4096-20:  # -20 for the rest of the option line.
        raise ValueError('Minified HTML longer than 4096-20 characters. Nginx will not load it.')

    location_gen = ('location ~* %s { if ($arg_raw) {break;} set $lang %s; try_files @highlight @highlight; }' % (regex, language)
                    for language, regex in languages.items() if language not in missing_languages)

    logging.info('Creating the config snippet...')
    return '\n'.join(filter(None, (
        '# NginxSourceViewer',
        '# -----------------',
        '# Requested languages: ' + ', '.join('%s: %s' % (k, v) for k, v in languages.items()),
        '# Requested styles: ' + ', '.join(styles),
        '# Missing languages: ' + (', '.join('%s: %s' % (k, v) for k, v in languages.items() if k in missing_languages) if missing_languages else 'None'),
        '# Missing styles: ' + (', '.join(missing_styles) if missing_styles else 'None'),
        *location_gen,
        'location @highlight {',
        '    if (!-f $request_filename) {',
        '        return 404;',
        '    }',
        '    charset UTF-8;',
        '    override_charset on;',
        '    source_charset UTF-8;',
        '    default_type text/html;',
        '    add_header Content-Type text/html;',
        '    return 200 \'%s\';' % html,
        '}',
    )))


def create_script_tag(lib, version, file):
    # Thanks https://tenzer.dk/generating-subresource-integrity-checksums/
    url = 'https://cdnjs.cloudflare.com/ajax/libs/%s/%s/%s' % (lib, version, file)
    return '<script src="%s"></script>' % url
    # This increases the HTML size too much.
    # integrity = 'sha256-%s' % base64.b64encode(hashlib.sha256(requests.get(url).text.encode()).digest()).decode()
    # return '<script src="%s" integrity="%s" crossorigin="anonymous"></script>' % (url, integrity)


def get_cdn_files(library):
    data = requests.get('https://api.cdnjs.com/libraries/%s?fields=assets' % library).json()
    logging.debug('Data on library %r: %r', library, data)
    return data['assets'][0]['version'], data['assets'][0]['files']


# Not used. The minified version is hardcoded. (Use https://cssminifier.com/)
MAGIC_CSS = '''
pre,html,body {
    min-height: 100%
}
.hljs {
    font-family: "Fira Code", monospace !important
} 
.wrap {
    white-space: pre-wrap; word-wrap: break-word;
}
td.hljs-ln-code {
    padding-left: 10px !important;
}
td.hljs-ln-numbers {
    user-select: none; text-align: right; color: #ccc; border-right: 1px solid #CCC; vertical-align: top; padding-right: 5px !important;
}
'''
MINIFIED_CSS = 'body,html,pre{min-height:100%}.hljs{font-family:"Fira Code",monospace!important}.wrap{' \
               'white-space:pre-wrap;word-wrap:break-word}td.hljs-ln-code{padding-left:10px!important}td.hljs-ln-numbers{' \
               'user-select:none;text-align:right;color:#ccc;border-right:1px solid #ccc;vertical-align:top;padding-right:5px!important} '
# Not used. The minified version is hardcoded. (Use https://javascript-minifier.com/)
MAGIC_JS = '''
const j = jQuery;
const ls = localStorage;
const RAW_URL = "$uri?raw=1";
var gStyle = STYLES[0];
hljs.configure({tabReplace: "    "});
function set_style(style) {
    j("#css").attr("href", j("#js").attr("src").replace(/lang.+/, "styles/"+style+".min.css"));
    j("#style").text(style.replace(/[-_]/g, " "));
    gStyle = style; ls.setItem("style", style);
}
function move_style(delta) {
    let i = (STYLES.indexOf(gStyle) + delta);
    if (i < 0) i += STYLES.length;
    set_style(STYLES[i % STYLES.length]);
}
function toggle_wrap() {
    let e = j("#code");
    let enable = arguments.length != 0 ? arguments[0] : !e.hasClass("wrap");
    if (enable) e.addClass("wrap");
    else e.removeClass("wrap");
    ls.setItem("wrap", enable);
}
j(function() {
    if (ls.getItem("style") !== null) set_style(ls.getItem("style"));
    else set_style(gStyle);
    if (ls.getItem("wrap") !== null) toggle_wrap(ls.getItem("wrap"));
    j.get({
        url: RAW_URL,
        dataType: "text"
    }).done(function(data) {
        let b = j("#code").text(data)[0];
        hljs.highlightBlock(b);
        hljs.lineNumbersBlock(b);
    });
    j("#nxtstyle").click(function() {move_style(+1);});
    j("#prvstyle").click(function() {move_style(-1);});
    j("#wrap").click(function() {toggle_wrap();});
});
'''
MINIFIED_JS = 'const j=jQuery,ls=localStorage,RAW_URL="$uri?raw=1";var gStyle=STYLES[0];function set_style(e){j("#css").attr("href",j("#js").attr(' \
              '"src").replace(/lang.+/,"styles/"+e+".min.css")),j("#style").text(e.replace(/[-_]/g," ")),gStyle=e,ls.setItem("style",' \
              'e)}function move_style(e){let t=STYLES.indexOf(gStyle)+e;t<0&&(t+=STYLES.length),set_style(STYLES[t%STYLES.length])}function toggle_wrap(){let '\
              'e=j("#code"),t=0!=arguments.length?arguments[0]:!e.hasClass("wrap");t?e.addClass("wrap"):e.removeClass("wrap"),ls.setItem("wrap",' \
              't)}hljs.configure({tabReplace:" "}),j(function(){null!==ls.getItem("style")?set_style(ls.getItem("style")):set_style(gStyle),' \
              'null!==ls.getItem("wrap")&&toggle_wrap(ls.getItem("wrap")),j.get({url:RAW_URL,dataType:"text"}).done(function(e){let t=j("#code").text(e)[' \
              '0];hljs.highlightBlock(t),hljs.lineNumbersBlock(t)}),j("#nxtstyle").click(function(){move_style(1)}),j("#prvstyle").click(function(){' \
              'move_style(-1)}),j("#wrap").click(function(){toggle_wrap()})});'

MAGIC_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="generator" content="NginxSourceViewer by Dries007: https://github.com/dries007/NginxSourceViewer">
    <link id="css" rel="stylesheet">
    <style>${css}</style>
    <title>$$uri</title>
</head>
<body class="hljs">
    ${scripts}
    <script id="js" src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/${highlight_version}/languages/$$lang.min.js"></script>
    <script>const STYLES=${styles};${js}</script>
    <div>
        <a href="./" class="hljs-subst">Show directory.</a>&nbsp;&nbsp;|&nbsp;&nbsp;
        <a href="$$uri?raw=1" class="hljs-subst">Get the raw file here.</a>&nbsp;&nbsp;|&nbsp;&nbsp;
        <a href="#" id="prvstyle" class="hljs-subst">&larr;</a>&nbsp;Style&nbsp;
        "<span id="style" style="text-transform: capitalize; display: inline-block; min-width: 20ch;"></span>"
        &nbsp;<a href="#" id="nxtstyle" class="hljs-subst">&rarr;</a>&nbsp;&nbsp;|&nbsp;&nbsp;
        <a href="#" id="wrap" class="hljs-subst">Toggle wrapping.</a>
    </div>
    <pre><code id="code" class="$$lang"></code></pre> </body>
</html>'''

if __name__ == '__main__':
    main()
