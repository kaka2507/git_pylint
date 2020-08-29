import os
import random
import shutil
import string


def is_python_file(path):
    return path.endswith('.py')


def second(_, y):
    return y


def extract_option(args, option_names, default_option, combine=second):
    option = default_option
    for i, arg in enumerate(args):
        for option_name in option_names:
            if arg and arg.startswith(option_name):
                if arg == option_name:
                    if i < len(args)-1:
                        option = combine(option, args[i+1])
                        args[i+1] = None
                elif option_name.startswith('--') and arg.startswith(option_name+'='):
                    option = combine(option, arg[len(option_name)+1:])
                elif not option_name.startswith('--'):
                    option = combine(option, arg[len(option_name):])
                else:
                    continue
                args[i] = None
                break

    args[:] = [arg for arg in args if arg is not None]
    return option


def get_line_count(path):
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def is_ignored(basename, ignore_names, ignore_patterns):
    for ignore_name in ignore_names:
        if ignore_name == basename:
            return True
    for ignore_pattern in ignore_patterns:
        if ignore_pattern.match(basename):
            return True
    return False


def mktemp(path):
    parent_dir, base = os.path.split(path)
    bottom_existing_dir = parent_dir
    while bottom_existing_dir and not os.path.isdir(bottom_existing_dir):
        bottom_existing_dir = os.path.dirname(bottom_existing_dir)
    if parent_dir and not os.path.isdir(parent_dir):
        os.makedirs(parent_dir)

    _, ext = os.path.splitext(base)
    has_created = False
    while not has_created:
        try:
            rand_str = ''.join(random.SystemRandom().choice(string.ascii_lowercase) for _ in range(10))
            temp_base = rand_str + ext
            temp_path = os.path.join(parent_dir, temp_base)
            os.close(os.open(temp_path, os.O_CREAT | os.O_EXCL))
            has_created = True
        except OSError:
            pass

    top_temp_path = temp_path
    while os.path.dirname(top_temp_path) != bottom_existing_dir:
        top_temp_path = os.path.dirname(top_temp_path)

    return temp_path, top_temp_path


def unpack_file(repo, blob, path=None):
    temp_path = repo.git.unpack_file(blob)
    shutil.move(temp_path, path)


def rmtree(path):
    try:
        os.remove(path)
    except OSError:
        shutil.rmtree(path)


def checkout(repo, tree):
    if repo.git.status(porcelain=True):
        raise RuntimeError('Directory not clean')
    repo.git.read_tree(tree)
    repo.git.checkout('--', os.curdir)
    repo.git.clean(d=True, force=True)
