from operator import methodcaller
from os import path, listdir
from xtermcolor import colorize

import atexit
import re
import readline
import shlex
import sys
import yaml



LEVELS = {'life': ('L', 0xff5f87),
          'domain': ('D', 0x87ff87),
          'kingdom': ('K', 0xffffff),
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
            'ls', 'pwd', 'p']


class Level:

    def __init__(self, basepath):
        self._path = basepath
        self._printed_prompt = False
        self._children = None
        self._ancestors = None

        with open(path.join(basepath, '.info.yml')) as f:
            self.info = yaml.load(f)
        self.info['name'] = path.basename(basepath)

        # Fill in paths of children and ancestors
        self.children_paths = [path.join(basepath, c)
                               for c in listdir(basepath)
                               if path.isdir(path.join(basepath, c))]
        self.ancestor_paths = []
        current  = path.dirname(self._path)
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
        return path.exists(path.join(path.dirname(self._path), '.info.yml'))

    def parent(self):
        if self.has_parent():
            return Level(path.dirname(self._path))
        raise Exception('Node has no parent')

    def _fill_children(self):
        if self._children is not None:
            return
        self._children = [Level(c) for c in self.children_paths]
        self._children.sort(key=methodcaller('name'))

    def _fill_ancestors(self):
        if self._ancestors is not None:
            return
        self._ancestors = [Level(c) for c in self.ancestor_paths]
        self._ancestors.sort(key=methodcaller('name'))


    # Output
    # =================================================================================

    def name(self):
        return self.info['name']

    def _level_short(self):
        return LEVELS[self.info['level']][0]

    def _level_color(self):
        return LEVELS[self.info['level']][1]

    def colorized_string(self):
        string = '[{short}] {name}'.format(short=self._level_short(),
                                           name=self.name())
        return colorize(string, rgb=self._level_color())

    def print_prompt(self, force=False):
        if self._printed_prompt and not force:
            return

        print(self.colorized_string())

        self._printed_prompt = True


    # Command parsing and execution
    # =================================================================================

    def command(self, command, *args):
        command = command.lower()

        # List children
        if command == 'ls':
            self._fill_children()
            for c in self._children:
                print(c.colorized_string())

        # List path from root
        if command == 'pwd':
            self._fill_ancestors()
            out = [c.colorized_string() for c in self._ancestors + [self]]
            print(' '.join([out[0]] + ['-> {next}'.format(next=c) for c in out[1:]]))

        # Go to ancestor
        if command == 'p':
            try:
                num = max(int(args[0]), 1)
            except IndexError:
                num = 1
            current = self
            while current.has_parent() and num > 0:
                current = current.parent()
            return current.refresh()

        # Go to another level by name
        matches = [c for c in self.children_paths + self.ancestor_paths
                   if path.basename(c).lower() == command.lower()]
        if len(matches) == 1:
            return Level(matches[0])


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
    level = Level(path.join(basepath, 'Life'))

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
