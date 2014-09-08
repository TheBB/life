from operator import methodcaller
from os import path, listdir
from textwrap import wrap
from xtermcolor import colorize

import atexit
import re
import readline
import shlex
import sys
import yaml



LEVELS = {'life': ('L', 0xff5f87),
          'domain': ('D', 0x87ff87),
          'kingdom': ('K', 0xffff87),
          'subkingdom': ('K-', 0xffffff),
          'superphylum': ('P+', 0xffffff),
          'phylum': ('P', 0xffffff),
          'subphylum': ('P-', 0xffffff),
          'superclass': ('C+', 0xffffff),
          'class': ('C', 0xffffff),
          'subclass': ('C-', 0xffffff),
          'superorder': ('O+', 0xffffff),
          'order': ('O', 0xffffff),
          'suborder': ('O-', 0xffffff),
          'superfamily': ('F+', 0xffffff),
          'family': ('F', 0xffffff),
          'subfamily': ('F-', 0xffffff),
          'genus': ('G', 0xffffff),
          'subgenus': ('G-', 0xffffff),
          'superspecies': ('S+', 0xffffff),
          'species': ('S', 0xffffff),
          'subspecies': ('S-', 0xffffff)}

COMMANDS = ['quit', 'exit',
            'ls', 'path', 'p']


class LightEntry:

    def __init__(self, basepath):
        self.path = basepath

        with open(path.join(basepath, '.info.yml')) as f:
            self.info = yaml.load(f)
        self.info['name'] = path.basename(basepath)

    def name(self):
        return self.info['name']

    def level_short(self):
        return LEVELS[self.info['level']][0]

    def level_color(self):
        return LEVELS[self.info['level']][1]

    def colorized_string(self):
        string = '[{short}] {name}'.format(short=self.level_short(),
                                           name=self.name())
        return colorize(string, rgb=self.level_color())


class Entry:

    def __init__(self, basepath):
        self.light = LightEntry(basepath)

        self._printed_prompt = False
        self._children = None
        self._ancestors = None

        # Fill in paths of children and ancestors
        self.children_paths = [path.join(basepath, c)
                               for c in listdir(basepath)
                               if path.isdir(path.join(basepath, c))]
        self.ancestor_paths = []
        current  = path.dirname(basepath)
        while path.exists(path.join(current, '.info.yml')):
            self.ancestor_paths.append(current)
            current = path.dirname(current)
        self.ancestor_paths = self.ancestor_paths[::-1]

        # Candidates for completion
        self._candidates = [path.basename(c) for c in self.children_paths + self.ancestor_paths]
        self._candidates.sort()

    def refresh(self):
        self._printed_prompt = False
        return self


    # Completion
    # =================================================================================

    def _complete(self, word, index):
        matches = [c for c in self._candidates + COMMANDS if re.match(word, c, re.I)]
        try:
            return matches[index] + " "
        except IndexError:
            return None

    def completer(self):
        return lambda word, index: self._complete(word, index)


    # Tree walking
    # =================================================================================

    def has_parent(self):
        return path.exists(path.join(path.dirname(self.light.path), '.info.yml'))

    def parent(self):
        if self.has_parent():
            return Entry(path.dirname(self.light.path))
        raise Exception('Node has no parent')

    def _fill_children(self):
        if self._children is not None:
            return
        self._children = [LightEntry(c) for c in self.children_paths]
        self._children.sort(key=methodcaller('name'))

    def _fill_ancestors(self):
        if self._ancestors is not None:
            return
        self._ancestors = [LightEntry(c) for c in self.ancestor_paths]


    # Output
    # =================================================================================

    def colorized_string(self):
        return self.light.colorized_string()

    def print_prompt(self, force=False):
        if self._printed_prompt and not force:
            return

        print(self.light.colorized_string())
        self._printed_prompt = True


    # Command parsing and execution
    # =================================================================================

    def command(self, command, *args):
        cmd = command.lower()

        # List children
        if cmd == 'ls':
            self._fill_children()
            for c in self._children:
                print(c.colorized_string())
            return self

        # List path from root
        if cmd == 'path':
            self._fill_ancestors()
            out = [c.colorized_string() for c in self._ancestors + [self]]
            print(' '.join([out[0]] + ['-> {next}'.format(next=c) for c in out[1:]]))
            return self

        # Go to ancestor
        if cmd == 'p':
            try:
                num = max(int(args[0]), 1)
            except IndexError:
                num = 1
            current = self
            while current.has_parent() and num > 0:
                current = current.parent()
                num -= 1
            return current.refresh()

        # Display info
        if cmd == '?':
            try:
                info = []
                for p in self.light.info['info'].split('\n'):
                    info += wrap('  ' + p)
                info = '\n'.join(info)
            except KeyError:
                info = colorize('No info for {name}'.format(name=self.name()), rgb=0xff0000)
            print(info)
            return self

        # Go to another level by name
        matches = [c for c in self.children_paths + self.ancestor_paths
                   if path.basename(c).lower() == cmd]
        if len(matches) == 1:
            return Entry(matches[0])

        # Unrecognized command
        print(colorize("Unrecognized command: '{cmd}'".format(cmd=cmd), rgb=0xff0000))
        return self


if __name__ == '__main__':
    basepath = path.dirname(path.realpath(__file__))

    # Initialize readline
    history_file = path.join(basepath, '.life_history')
    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        pass
    atexit.register(readline.write_history_file, history_file)
    readline.parse_and_bind('tab: complete')

    # Start at the root
    level = Entry(path.join(basepath, 'Life'))

    # Main program loop
    while True:
        readline.set_completer(level.completer())

        try:
            level.print_prompt()
            command = shlex.split(input('> '))

            if command[0] == 'quit' or command[0] == 'exit':
                sys.exit(0)

            level = level.command(*command)
        except EOFError:
            print('')
            break
        except KeyboardInterrupt:
            print('')
            continue
