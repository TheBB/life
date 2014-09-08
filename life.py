#!/bin/env python3

from glob import iglob
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


help_colorize = lambda s: colorize(s, rgb=0xff5f87)
arg_colorize = lambda s: colorize(s, rgb=0x87ff87)

help_entries = [('help', 'Show this guide.'),
                ('exit', 'Exit program.'),
                ('ls', '\n'.join(['Search for nodes. Available arguments are:',
                                  '  {a}: search a distance {b} down the tree'
                                  .format(a=arg_colorize('-d<num>'),
                                          b=arg_colorize('<num>')),
                                  '  {a}: search a range of distances'
                                  .format(a=arg_colorize('-d<num1>..<num2>')),
                                  '  {a}: search for nodes on a specific level'
                                  .format(a=arg_colorize('-l<level>')),
                                  '  {a}: part of the name of the node'
                                  .format(a=arg_colorize('<text>')),
                                  '  With no arguments, defauls to {a}.'
                                  .format(a=arg_colorize('-d1'))])),
                ('goto', "Go to node. Takes the same arguments as `ls'."),
                ('p {a}'.format(a=arg_colorize('<num>')),
                 'Go {a} levels higher. {a} defaults to 1.'.format(a=arg_colorize('<num>'))),
                ('path', 'Show the current location as a path from root.'),
                ('?', 'Show information about the current node.'),
                ('<node>', 'Jump directly to an ancestor or direct child by name.')]

help_string = '\n'.join(['{cmd}: {exp}'.format(cmd=help_colorize(cmd), exp=exp)
                         for cmd, exp in help_entries])


LEVELS = {'life':          (0, 'L',  0xff5f87),
          'domain':        (1, 'D',  0x87ff87),
          'kingdom':       (2, 'K',  0xffff5f),
          'subkingdom':    (3, 'K-', 0x5fafff),
          'superphylum':   (4, 'P+', 0xffff5f),
          'phylum':        (5, 'P',  0xd75fff),
          'subphylum':     (6, 'P-', 0xffffff),
          'superclass':    (7, 'C+', 0xffffff),
          'class':         (8, 'C',  0xdadada),
          'subclass':      (9, 'C-', 0xffffff),
          'superorder':   (10, 'O+', 0xffffff),
          'order':        (11, 'O',  0xffffff),
          'suborder':     (13, 'O-', 0xffffff),
          'superfamily':  (14, 'F+', 0xffffff),
          'family':       (15, 'F',  0xffffff),
          'subfamily':    (16, 'F-', 0xffffff),
          'genus':        (17, 'G',  0xffffff),
          'subgenus':     (18, 'G-', 0xffffff),
          'superspecies': (19, 'S+', 0xffffff),
          'species':      (20, 'S',  0xffffff),
          'subspecies':   (21, 'S-', 0xffffff)}

COMMANDS = ['exit',
            'ls', 'goto', 'path', 'p', '?']


def level_dict():
    return {level: set() for level in LEVELS}

def distance_dict():
    return {distance: set() for distance in range(len(LEVELS))}

def parse_level(s):
    for k, v in LEVELS.items():
        if k == s.lower() or v[1] == s.upper():
            return k


# Represents one node in the tree (light operations only)
# =================================================================================

class LightEntry:

    def __init__(self, basepath):
        self.path = basepath

        with open(path.join(basepath, '.info.yml')) as f:
            self.info = yaml.load(f)
        self.info['name'] = path.basename(basepath)

    def name(self):
        return self.info['name']

    def level(self):
        return self.info['level']

    def level_short(self):
        return LEVELS[self.info['level']][1]

    def level_color(self):
        return LEVELS[self.info['level']][2]

    def colorized_string(self):
        string = '[{short}] {name}'.format(short=self.level_short(),
                                           name=self.name())
        if 'common' in self.info:
            string += ' ({common})'.format(common=self.info['common'])
        return colorize(string, rgb=self.level_color())

    def has_parent(self):
        return path.exists(path.join(path.dirname(self.path), '.info.yml'))

    def parent(self):
        return LightEntry(path.dirname(self.path))

    def full(self):
        return Entry(self.path)



# Represents one node in the tree
# =================================================================================

class Entry:

    def __init__(self, basepath):
        self.light = LightEntry(basepath)

        self._printed_prompt = False
        self._ancestors = None

        self._path_cache = set()
        self._children_by_distance = distance_dict()
        self._children_by_name = {}
        self._children_by_level = level_dict()
        self._levels_searched = set()
        self._distances_searched = set()

        self._fill_distance(1)

        self._ancestors = []
        try:
            current = self.light.parent()
            self._ancestors.append(current)
            while True:
                current = current.parent()
                self._ancestors.append(current)
        except FileNotFoundError:
            pass
        self._ancestors = self._ancestors[::-1]

        # Candidates for completion
        self._candidates = [e.name() for e in self._children_by_distance[1] | set(self._ancestors)]
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

    def _add_entry(self, entry, distance):
        self._children_by_distance[distance].add(entry)
        self._children_by_level[entry.info['level']].add(entry)
        self._children_by_name[entry.name()] = entry

    def _get_new_paths(self, distance):
        return set(filter(path.isdir, iglob(self.light.path + ''.join('/*'*distance)))) - self._path_cache

    def _fill_distance(self, *distances):
        for d in set(distances) - self._distances_searched:
            self._distances_searched.add(d)
            paths = self._get_new_paths(d)
            for basepath in paths:
                self._add_entry(LightEntry(basepath), d)
            self._path_cache.update(paths)

    def _fill_level(self, *levels):
        levels = set(levels)

        max_dist = 0
        for l in set(levels) - self._levels_searched:
            self._levels_searched.add(l)
            max_dist = max(LEVELS[l][0] - LEVELS[self.light.level()][0], max_dist)

        distances = set(range(1, max_dist+1)) - self._distances_searched
        for d in distances:
            paths = self._get_new_paths(d)
            for basepath in paths:
                entry = LightEntry(basepath)
                if entry.level() in levels:
                    self._add_entry(entry, d)
                    self._path_cache.add(entry.path)

    def parent(self):
        if self.light.has_parent():
            return Entry(path.dirname(self.light.path))
        raise Exception('Node has no parent')


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

        # List path from root
        if cmd == 'path':
            out = [c.colorized_string() for c in self._ancestors + [self]]
            print(' '.join([out[0]] + ['-> {next}'.format(next=c) for c in out[1:]]))
            return self

        # Find and goto
        if cmd in ['ls', 'goto']:
            distances = set()
            levels = set()
            names = set()
            for arg in args:

                # Search by distance
                if arg.startswith('-d'):
                    try:
                        distances.add(int(arg[2:]))
                        continue
                    except ValueError:
                        pass

                    try:
                        init, fin = map(int, arg[2:].split('..'))
                        distances.update(set(range(init, fin+1)))
                        continue
                    except ValueError:
                        print(colorize("Couldn't parse argument '{arg}'".format(arg=arg), rgb=0xff0000))
                        return self

                # Search by level
                if arg.startswith('-l'):
                    level = parse_level(arg[2:])
                    if level:
                        levels.add(level)
                        continue
                    else:
                        print(colorize("No such level '{level}'".format(level=arg[2:]), rgb=0xff0000))
                        return self

                # Search by name
                names.add(arg)

            if not (distances or levels):
                distances = {1}

            self._fill_distance(*distances)
            self._fill_level(*levels)

            distance_cands = set()
            level_cands = set()
            for d in distances:
                distance_cands |= self._children_by_distance[d]
            for l in levels:
                level_cands |= self._children_by_level[l]

            if distances and levels:
                candidates = distance_cands & level_cands
            else:
                candidates = distance_cands or level_cands

            matches = [c for c in candidates if all(re.search(arg, c.name(), re.I) for arg in names)]

            if cmd == 'goto':
                if len(matches) == 1:
                    return matches[0].full()
                else:
                    print(colorize("No unique entry found:", rgb=0xff0000))

            matches.sort(key=methodcaller('name'))
            for c in matches:
                print(c.colorized_string())

            return self

        # Go to ancestor
        if cmd == 'p':
            try:
                num = max(int(args[0]), 1)
            except IndexError:
                num = 1
            except:
                print(colorize("Unable to parse as number: '{arg}'".format(arg=args[0]), rgb=0xff0000))
                return self

            current = self.light
            while current.has_parent() and num > 0:
                current = current.parent()
                num -= 1
            return current.full()

        # Display info
        if cmd == '?':
            try:
                info = []
                for p in self.light.info['info'].split('\n'):
                    info += wrap('  ' + p)
                info = '\n'.join(info)
            except KeyError:
                info = colorize('No info for {name}'.format(name=self.light.name()), rgb=0xff0000)
            print(info)
            return self

        # Go to another entry by name
        matches = [c for c in self._children_by_distance[1] | set(self._ancestors)
                   if c.name().lower() == cmd]
        if len(matches) == 1:
            return Entry(matches[0].path)

        # Unrecognized command
        print(colorize("Unrecognized command: '{cmd}'".format(cmd=cmd), rgb=0xff0000))
        return self


# Main program
# =================================================================================

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

            if not command:
                continue

            if command[0] in ['exit']:
                break
            elif command[0] == 'help':
                print(help_string)
                continue

            level = level.command(*command)

        except EOFError:
            print('')
            break

        except KeyboardInterrupt:
            print('')
            continue
