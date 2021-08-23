import os
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Tuple
from unittest.mock import patch

import pytest
from mock import patch

import megfile
from megfile import smart
from megfile.interfaces import Access, StatResult
from megfile.s3 import _s3_binary_mode
from megfile.smart_path import SmartPath


@pytest.fixture
def filesystem(fs):
    return fs


@patch.object(SmartPath, "listdir")
def test_smart_listdir(funcA):
    ret = ["ret value1", "ret value2"]
    funcA.return_value = ret
    res = smart.smart_listdir("Test Case")
    assert res == ret
    funcA.assert_called_once()


@patch.object(SmartPath, "scandir")
def test_smart_scandir(funcA):
    smart.smart_scandir("Test Case")
    funcA.assert_called_once()


@patch.object(SmartPath, 'getsize')
def test_smart_getsize(funcA):
    funcA.return_value = 0
    res = smart.smart_getsize("Test Case")
    assert res == 0
    funcA.assert_called_once()


@patch.object(SmartPath, 'md5')
def test_smart_getmd5(funcA):
    funcA.return_value = 'dcddb75469b4b4875094e14561e573d8'
    res = smart.smart_getmd5("Test Case")
    assert res == 'dcddb75469b4b4875094e14561e573d8'
    funcA.assert_called_once()


@patch.object(SmartPath, 'getmtime')
def test_smart_getmtime(funcA):
    funcA.return_value = 0.0
    res = smart.smart_getmtime("Test Case")
    assert res == 0.0
    funcA.assert_called_once()


@patch.object(SmartPath, 'stat')
def test_smart_stat(funcA):
    funcA.return_value = StatResult()
    res = smart.smart_stat("Test Case")
    assert res == StatResult()
    funcA.assert_called_once()


@patch.object(SmartPath, 'is_dir')
def test_smart_isdir(funcA):
    funcA.return_value = True
    res = smart.smart_isdir("True Case")
    assert res == True
    funcA.assert_called_once()
    funcA.return_value = False
    res = smart.smart_isdir("False Case")
    assert res == False
    assert funcA.call_count == 2


@patch.object(SmartPath, 'is_file')
def test_smart_isfile(funcA):
    funcA.return_value = True
    res = smart.smart_isfile("True Case")
    assert res == True
    funcA.assert_called_once()
    funcA.return_value = False
    res = smart.smart_isfile("False Case")
    assert res == False
    assert funcA.call_count == 2


@patch.object(SmartPath, 'exists')
def test_smart_exists(funcA):
    funcA.return_value = True
    res = smart.smart_exists("True Case")
    assert res == True
    funcA.assert_called_once()
    funcA.return_value = False
    res = smart.smart_exists("False Case")
    assert res == False
    assert funcA.call_count == 2


@patch.object(SmartPath, 'is_symlink')
def test_smart_islink(funcA):
    funcA.return_value = True
    res = smart.smart_islink("True Case")
    assert res == True
    funcA.assert_called_once()
    funcA.return_value = False
    res = smart.smart_islink("False Case")
    assert res == False
    assert funcA.call_count == 2


@patch.object(SmartPath, 'access')
def test_smart_access(funcA):
    funcA.return_value = True
    s3_path = "s3://test"
    readBucket = smart.smart_access(s3_path, mode=Access.READ)
    writeBucket = smart.smart_access(s3_path, mode=Access.WRITE)
    file_path = 'file'
    readFile = smart.smart_access(file_path, mode=Access.READ)
    writeFile = smart.smart_access(file_path, Access.WRITE)
    assert readBucket == True
    assert writeBucket == True
    assert readFile == True
    assert writeFile == True
    assert funcA.call_count == 4


def test_smart_copy(mocker):

    def is_symlink(path: str) -> bool:
        return path == 'link'

    s3_copy = mocker.patch('megfile.smart.s3_copy')
    s3_download = mocker.patch('megfile.smart.s3_download')
    s3_upload = mocker.patch('megfile.smart.s3_upload')
    fs_copy = mocker.patch('megfile.smart.fs_copy')
    copyfile = mocker.patch('megfile.fs._copyfile')

    smart_islink = mocker.patch(
        'megfile.smart.smart_islink', side_effect=is_symlink)

    patch_dict = {
        's3': {
            's3': s3_copy,
            'file': s3_download
        },
        'file': {
            's3': s3_upload,
            'file': fs_copy,
        }
    }

    with patch('megfile.smart._copy_funcs', patch_dict) as _:

        smart.smart_copy('link', 's3://a/b')
        assert s3_copy.called is False
        assert s3_download.called is False
        assert s3_upload.called is False
        assert fs_copy.called is False

        smart.smart_copy('s3://a/b', 's3://a/b')
        s3_copy.assert_called_once_with('s3://a/b', 's3://a/b', callback=None)

        smart.smart_copy('s3://a/b', 'fs')
        s3_download.assert_called_once_with('s3://a/b', 'fs', callback=None)

        smart.smart_copy('fs', 's3://a/b')
        s3_upload.assert_called_once_with('fs', 's3://a/b', callback=None)

        fs_stat = mocker.patch(
            'megfile.fs.fs_stat', return_value=StatResult(islnk=False, size=10))
        smart.smart_copy('fs', 'fs')
        fs_copy.assert_called_once_with('fs', 'fs', callback=None)
        fs_copy.reset_mock()
        fs_stat.stop()


def test_smart_copy_fs2fs(mocker):
    fs_makedirs = mocker.patch(
        'megfile.fs.fs_makedirs', side_effect=lambda *args, **kwargs:...)

    class fake_copy:
        flag = False

        def __call__(self, *args, **kwargs):
            if self.flag:
                return
            else:
                error = FileNotFoundError()
                error.filename = 'fs/a/b/c'
                self.flag = True
                raise error

    copyfile = mocker.patch('megfile.fs._copyfile')
    copyfile.side_effect = fake_copy()
    smart.smart_copy('fs', 'fs/a/b/c')
    fs_makedirs.call_count == 1
    fs_makedirs.assert_called_once_with('fs/a/b', exist_ok=True)
    fs_makedirs.reset_mock()


def test_smart_copy_UP2UP(filesystem):

    patch_dict = {}
    with patch('megfile.smart._copy_funcs', patch_dict) as _:
        data = b'test'
        with smart.smart_open('a', 'wb') as writer:
            writer.write(data)
        smart.smart_copy('a', 'b')
        assert data == smart.smart_open('b', 'rb').read()


def test_smart_sync(mocker):

    def isdir(path: str) -> bool:
        return os.path.basename(path).startswith('folder')

    def isfile(path: str) -> bool:
        return os.path.basename(path).startswith('file')

    smart_copy = mocker.patch('megfile.smart.smart_copy')
    smart_isdir = mocker.patch('megfile.smart.smart_isdir', side_effect=isdir)
    smart_isfile = mocker.patch(
        'megfile.smart.smart_isfile', side_effect=isfile)
    smart_scan = mocker.patch('megfile.smart.smart_scan')
    '''
      folder/
        - folderA/
          -fileB
        - fileA
      - a/
        - b/
          - c
        - d
      - a
    '''

    def listdir(path: str):
        if path == 'folder':
            return ["folder/folderA/fileB", "folder/fileA"]
        if path == 'folder/fileA':
            return ["folder/fileA"]
        if path == 'a':
            return ['a', 'a/b/c', 'a/d']

    smart_scan.side_effect = listdir

    smart.smart_sync('folder', 'dst')
    assert smart_copy.call_count == 2
    smart_copy.assert_any_call('folder/fileA', 'dst/fileA', callback=None)
    smart_copy.assert_any_call(
        'folder/folderA/fileB', 'dst/folderA/fileB', callback=None)
    smart_copy.reset_mock()

    smart.smart_sync('folder/fileA', 'dst/file')
    assert smart_copy.call_count == 1
    smart_copy.assert_any_call('folder/fileA', 'dst/file', callback=None)
    smart_copy.reset_mock()

    smart.smart_sync('a', 'dst')
    assert smart_copy.call_count == 3
    smart_copy.assert_any_call('a', 'dst', callback=None)
    smart_copy.assert_any_call('a/b/c', 'dst/b/c', callback=None)
    smart_copy.assert_any_call('a/d', 'dst/d', callback=None)


@patch.object(SmartPath, 'remove')
def test_smart_remove(funcA):
    funcA.return_value = None

    res = smart.smart_remove("False Case", False)
    assert res is None
    funcA.assert_called_once_with(missing_ok=False)

    res = smart.smart_remove("True Case", True)
    assert res is None
    funcA.assert_called_with(missing_ok=True)


@patch.object(SmartPath, 'rename')
def test_smart_move(funcA):
    funcA.return_value = None
    res = smart.smart_move('s3://bucket/a', 's3://bucket/b')
    assert res is None
    funcA.assert_called_once_with('s3://bucket/b')


@patch.object(SmartPath, 'rename')
def test_smart_rename(funcA):
    funcA.return_value = None
    res = smart.smart_move('s3://bucket/a', 's3://bucket/b')
    assert res is None
    funcA.assert_called_once_with('s3://bucket/b')


@patch.object(SmartPath, 'unlink')
def test_smart_unlink(funcA):
    funcA.return_value = None

    res = smart.smart_unlink("False Case", False)
    assert res is None
    funcA.assert_called_once_with(missing_ok=False)

    res = smart.smart_unlink("True Case", True)
    assert res is None
    funcA.assert_called_with(missing_ok=True)


@patch.object(SmartPath, 'makedirs')
def test_smart_makedirs(funcA):
    funcA.return_value = None
    res = smart.smart_makedirs("Test Case", exist_ok=True)
    assert res is None
    funcA.assert_called_once_with(True)


def test_smart_open(mocker, fs):
    '''
    This test is pretty naïve. Feel free to improve it
    in order to ensure smart_open works as we expected.

    Even ourselves do not know what we expect up to now.
    '''
    """
    s3_writer = mocker.patch('megfile.s3.S3BufferedWriter')
    s3_reader = mocker.patch('megfile.s3.S3PrefetchReader')
    fs_open = mocker.patch('io.open', side_effect=open)
    text_wrapper = mocker.patch('io.TextIOWrapper')
    is_s3_func = mocker.patch('megfile.smart.is_s3')
    fs_isdir_func = mocker.patch('megfile.smart.fs_isdir')
    s3_isdir_func = mocker.patch('megfile.smart.s3_isdir')
    s3_isfile_func = mocker.patch('megfile.smart.s3_isfile')
    parse_s3_url = mocker.patch('megfile.s3.parse_s3_url')
    mocker.patch('megfile.s3.get_s3_client')


    is_s3_func.return_value = False
    fs_isdir_func.return_value = True

    with pytest.raises(IsADirectoryError):
        smart.smart_open('folder')
        """
    """
    is_s3_func.return_value = False
    fs_isdir_func.return_value = False
    with pytest.raises(FileNotFoundError):
        smart.smart_open('non-exist.file')
    fs_open.side_effect = None
    fs_open.reset_mock()

    is_s3_func.return_value = False
    fs_isdir_func.return_value = False
    smart.smart_open('file', 'wb+')
    fs_open.assert_called_once_with('file', 'wb+', encoding=None, errors=None)
    fs_open.reset_mock()

    is_s3_func.return_value = False
    fs_isdir_func.return_value = False
    smart.smart_open('non-exist/file', 'wb')
    fs_open.assert_called_once_with(
        'non-exist/file', 'wb', encoding=None, errors=None)
    fs_open.reset_mock()

    is_s3_func.return_value = True
    s3_isdir_func.return_value = True
    s3_isfile_func.return_value = True
    parse_s3_url.return_value = ('bucket', 'key')
    smart.smart_open('s3://bucket/key')
    s3_reader.side_effect = None
    s3_reader.reset_mock()
    text_wrapper.reset_mock()

    is_s3_func.return_value = True
    s3_isdir_func.return_value = True
    s3_isfile_func.return_value = False
    parse_s3_url.return_value = ('bucket', 'key')
    with pytest.raises(IsADirectoryError) as e:
        smart.smart_open('s3://bucket/key')

    is_s3_func.return_value = True
    s3_isdir_func.return_value = False
    s3_isfile_func.return_value = False
    parse_s3_url.return_value = ('bucket', 'key')
    with pytest.raises(FileNotFoundError) as e:
        smart.smart_open('s3://bucket/key')

    is_s3_func.return_value = True
    s3_isdir_func.return_value = True
    s3_isfile_func.return_value = True
    parse_s3_url.return_value = ('bucket', 'key')
    with pytest.raises(FileExistsError) as e:
        smart.smart_open('s3://bucket/key', 'x')

    is_s3_func.return_value = True
    s3_isdir_func.return_value = False
    s3_isfile_func.return_value = False
    parse_s3_url.return_value = ('bucket', 'key')
    with pytest.raises(ValueError) as e:
        smart.smart_open('s3://bucket/key', 'wb+')
    assert 'wb+' in str(e.value)

    is_s3_func.return_value = True
    s3_isdir_func.return_value = False
    s3_isfile_func.return_value = False
    parse_s3_url.return_value = ('bucket', 'key')
    smart.smart_open('s3://bucket/key', 'w')
    # s3_writer.assert_called_once() in Python 3.6+
    assert s3_writer.call_count == 1
    # text_wrapper.assert_called_once() in Python 3.6+
    assert text_wrapper.call_count == 1
    s3_writer.reset_mock()
    text_wrapper.reset_mock()

    is_s3_func.return_value = True
    s3_isdir_func.return_value = False
    s3_isfile_func.return_value = False
    parse_s3_url.return_value = ('bucket', 'key')
    smart.smart_open('s3://bucket/key', 'xb')
    # s3_writer.assert_called_once() in Python 3.6+
    assert s3_writer.call_count == 1
    # text_wrapper.assert_not_called() in Python 3.6+
    assert text_wrapper.call_count == 0
    s3_writer.reset_mock()
    text_wrapper.reset_mock()

    is_s3_func.return_value = True
    s3_isdir_func.return_value = False
    s3_isfile_func.return_value = True
    parse_s3_url.return_value = ('bucket', 'key')
    smart.smart_open('s3://bucket/key', 'r')
    # s3_reader.assert_called_once() in Python 3.6+
    assert s3_reader.call_count == 1
    # text_wrapper.assert_called_once() in Python 3.6+
    assert text_wrapper.call_count == 1
    s3_reader.reset_mock()
    text_wrapper.reset_mock()
    """


def test_smart_open_custom_s3_open_func(mocker, fs):
    s3_open = mocker.Mock()
    s3_binary_open = _s3_binary_mode(s3_open)
    text_wrapper = mocker.patch('io.TextIOWrapper')
    s3_hasbucket_func = mocker.patch('megfile.s3.s3_hasbucket')
    s3_hasbucket_func.return_value = True
    s3_isfile_func = mocker.patch('megfile.s3.s3_isfile')
    s3_isfile_func.return_value = False
    parse_s3_url = mocker.patch('megfile.s3.parse_s3_url')
    parse_s3_url.return_value = ('bucket', 'key')

    smart.smart_open('s3://bucket/key', 'r', s3_open_func=s3_binary_open)
    s3_open.assert_called_once_with('s3://bucket/key', 'rb')
    # text_wrapper.assert_called_once() in Python 3.6+
    assert text_wrapper.call_count == 1
    s3_open.reset_mock()
    text_wrapper.reset_mock()

    smart.smart_open('s3://bucket/key', 'wt', s3_open_func=s3_binary_open)
    s3_open.assert_called_once_with('s3://bucket/key', 'wb')
    # text_wrapper.assert_called_once() in Python 3.6+
    assert text_wrapper.call_count == 1
    s3_open.reset_mock()
    text_wrapper.reset_mock()

    smart.smart_open('s3://bucket/key', 'wb', s3_open_func=s3_binary_open)
    s3_open.assert_called_once_with('s3://bucket/key', 'wb')
    # text_wrapper.assert_not_called() in Python 3.6+
    assert text_wrapper.call_count == 0
    s3_open.reset_mock()
    text_wrapper.reset_mock()

    smart.smart_open('s3://bucket/key', 'ab+', s3_open_func=s3_binary_open)
    s3_open.assert_called_once_with('s3://bucket/key', 'ab+')
    # text_wrapper.assert_not_called() in Python 3.6+
    assert text_wrapper.call_count == 0
    s3_open.reset_mock()
    text_wrapper.reset_mock()

    smart.smart_open('s3://bucket/key', 'x', s3_open_func=s3_binary_open)
    s3_open.assert_called_once_with('s3://bucket/key', 'wb')
    # text_wrapper.assert_not_called() in Python 3.6+
    assert text_wrapper.call_count == 1
    s3_open.reset_mock()
    text_wrapper.reset_mock()

    with pytest.raises(FileNotFoundError):
        s3_hasbucket_func.return_value = False
        smart.smart_open('s3://bucket/key', 'wt', s3_open_func=s3_binary_open)

    with pytest.raises(FileExistsError):
        s3_isfile_func.return_value = True
        smart.smart_open('s3://bucket/key', 'x', s3_open_func=s3_binary_open)


@patch.object(SmartPath, "joinpath", return_value=Path())
def test_smart_path_join(funcA):
    res = smart.smart_path_join(
        "s3://Test Case1", "s3://Test Case2", "s3://Test Case3")
    funcA.assert_called_once_with("s3://Test Case2", "s3://Test Case3")


def test_smart_path_join_result():
    assert smart.smart_path_join('path') == 'path'
    assert smart.smart_path_join('path', 'to/file') == 'path/to/file'
    assert smart.smart_path_join('path', 'to//file') == 'path/to/file'
    assert smart.smart_path_join('path', 'to', 'file') == 'path/to/file'
    assert smart.smart_path_join('path', 'to/', 'file') == 'path/to/file'
    assert smart.smart_path_join('path', 'to', '/file') == '/file'
    assert smart.smart_path_join('path', 'to', 'file/') == 'path/to/file'
    assert smart.smart_path_join('s3://') == 's3://'
    assert smart.smart_path_join('s3://', 'bucket/key') == 's3://bucket/key'
    assert smart.smart_path_join('s3://', 'bucket//key') == 's3://bucket//key'
    assert smart.smart_path_join('s3://', 'bucket', 'key') == 's3://bucket/key'
    assert smart.smart_path_join('s3://', 'bucket/', 'key') == 's3://bucket/key'
    assert smart.smart_path_join('s3://', 'bucket', '/key') == 's3://bucket/key'
    assert smart.smart_path_join(
        's3://', 'bucket', 'key/') == 's3://bucket/key/'


@patch.object(SmartPath, "walk")
def test_smart_walk(funcA):
    funcA.return_value = None
    res = smart.smart_walk("Test Case")
    assert res is None
    funcA.assert_called_once()


@patch.object(SmartPath, "scan")
def test_smart_scan(funcA):
    smart.smart_scan("Test Case")
    funcA.assert_called_once()


@patch.object(SmartPath, "scan_stat")
def test_smart_scan_stat(funcA):
    smart.smart_scan_stat("Test Case")
    funcA.assert_called_once()


@patch.object(SmartPath, "glob")
def test_smart_glob(funcA):
    smart.smart_glob('s3://bucket/*')
    funcA.assert_called_once()


@patch.object(SmartPath, "glob")
def test_smart_glob_cross_backend(funcA):
    # sublist = [1,2,3]
    # funcA.return_value = iter(sublist)
    res = smart.smart_glob(r'{/a,s3://bucket/key}/filename')
    assert funcA.call_count == 2
    # assert list(res) == sublist*2


@patch.object(SmartPath, "iglob")
def test_smart_iglob(funcA):
    smart.smart_iglob('s3://bucket/*')
    funcA.assert_called_once()


@patch.object(SmartPath, "iglob")
def test_smart_iglob_cross_backend(funcA):
    smart.smart_iglob(r'{/a,s3://bucket/key,s3://bucket2/key}/filename')
    assert funcA.call_count == 2


@patch.object(SmartPath, "glob_stat")
def test_smart_glob_stat(funcA):
    smart.smart_glob_stat('s3://bucket/*')
    funcA.assert_called_once()


@patch.object(SmartPath, "glob_stat")
def test_smart_glob_stat_cross_backend(funcA):
    smart.smart_glob_stat(r'{/a,s3://bucket/key,s3://bucket2/key}/filename')
    assert funcA.call_count == 2


def test_smart_save_as(mocker):
    funcA = mocker.patch('megfile.s3.s3_save_as')
    funcB = mocker.patch('megfile.fs.fs_save_as')
    stream = BytesIO()
    smart.smart_save_as(stream, 's3://test/ture_case')
    funcA.assert_called_once_with(stream, 's3://test/ture_case')
    smart.smart_save_as(stream, '/test/false_case')
    funcB.assert_called_once_with(stream, '/test/false_case')


@patch.object(SmartPath, "load")
def test_smart_load_from(funcA):
    smart.smart_load_from('Test Case')
    funcA.assert_called_once()


@pytest.fixture
def s3_path():
    yield 's3://bucket/test'


@pytest.fixture
def abs_path(fs):
    fs.create_file(os.path.join(os.path.dirname(__file__), 'test'))
    yield os.path.join(os.path.dirname(__file__), 'test')


@pytest.fixture
def rel_path(fs):
    fs.create_file('./test')
    yield 'test'


@pytest.fixture
def link_path(fs, abs_path):
    fs.create_symlink('link', abs_path)
    yield 'link'


@pytest.fixture
def mount_point(fs):
    fs.add_mount_point(os.path.dirname(__file__))
    yield os.path.dirname(__file__)


def test_smart_isabs(s3_path, abs_path, rel_path):
    assert smart.smart_isabs(s3_path) is True
    assert smart.smart_isabs(abs_path) is True
    assert smart.smart_isabs(rel_path) is False


def test_smart_ismount(mount_point, s3_path, abs_path):
    assert smart.smart_ismount(s3_path) is False
    assert smart.smart_ismount(abs_path) is False
    assert smart.smart_ismount(mount_point) is True


def test_smart_abspath(mocker, s3_path, abs_path, rel_path):
    mocker.patch('os.getcwd', return_value=os.path.dirname(__file__))
    assert smart.smart_abspath(s3_path) == s3_path
    assert smart.smart_abspath(rel_path) == abs_path


def test_smart_realpath(s3_path, abs_path, link_path):
    assert smart.smart_realpath(s3_path) == s3_path
    assert smart.smart_realpath(abs_path) == abs_path
    assert smart.smart_realpath(link_path) == abs_path


def test_smart_relpath(mocker, s3_path, abs_path, rel_path):
    mocker.patch('os.getcwd', return_value=os.path.dirname(__file__))
    assert smart.smart_relpath(s3_path) == s3_path
    assert smart.smart_relpath(abs_path, os.path.dirname(__file__)) == rel_path


def test_smart_load_image_metadata(mocker):
    s3_load_content = mocker.patch('megfile.smart.s3_load_content')
    s3_isfile = mocker.patch(
        'megfile.s3_path.S3Path.is_file', return_value=True)
    s3_stat = mocker.patch('megfile.smart.smart_getsize', return_value=22228)

    def _fake_load_content(*args, **kwargs):
        return open('tests/lib/lookmanodeps.png', 'rb').read()

    s3_load_content.side_effect = _fake_load_content

    res = smart.smart_load_image_metadata("s3://bucket/key")

    assert res.path == 's3://bucket/key'
    assert res.type == 'PNG'
    assert res.file_size == 22228
    assert res.width == 251
    assert res.height == 208


def test_smart_open_stdin(mocker):
    stdin_buffer_read = mocker.patch('sys.stdin.buffer.read')
    stdin_buffer_read.return_value = b'test\ntest1\n'

    reader = megfile.smart_open('stdio://-', 'r')
    assert reader.read() == 'test\ntest1\n'


def test_smart_open_stdout(mocker):
    # TODO: 这里 pytest 会把 sys.stdout mocker 掉，导致无法测试，之后想办法解决
    return
    data = BytesIO()

    def fake_write(w_data):
        data.write(w_data)
        return len(w_data)

    mocker.patch('_io.FileIO', side_effect=fake_write)
    writer = megfile.smart_open('stdio://-', 'w')
    writer.write('test')
    assert data.getvalue() == b'test'


def test_smart_load_content():
    path = 'tests/lib/lookmanodeps.png'
    content = open(path, 'rb').read()

    assert smart.smart_load_content(path) == content
    assert smart.smart_load_content(path, 1) == content[1:]
    assert smart.smart_load_content(path, stop=-1) == content[:-1]
    assert smart.smart_load_content(path, 4, 7) == content[4:7]

    with pytest.raises(Exception) as error:
        smart.smart_load_content(path, 5, 2)


def test_smart_save_content(mocker):
    content = 'test data for smart_save_content'
    smart_open = mocker.patch('megfile.smart.smart_open')


def test_smart_load_text(mocker):
    test = 'test data for smart_load_text'
    smart_open = mocker.patch('megfile.smart.smart_open')


def test_smart_save_text(mocker):
    content = 'test data for smart_save_text'

    smart_open = mocker.patch('megfile.smart.smart_open')

    def _fake_smart_open(*args, **kwargs):
        return StringIO(content)

    smart_open.side_effect = _fake_smart_open

    assert smart.smart_load_text('s3://bucket/key') == content

    with pytest.raises(Exception) as error:
        smart.smart_load_text('s3://bucket/key', 5, 2)


def test_register_copy_func():
    test = lambda *args, **kwargs:...
    smart.register_copy_func('a', 'b', test)
    assert smart._copy_funcs['a']['b'] == test

    with pytest.raises(ValueError) as error:
        smart.register_copy_func('a', 'b', test)

    assert error.value.args[0] == 'Copy Function has already existed: a->b'


def test_smart_cache(mocker):
    from megfile.interfaces import NullCacher
    from megfile.lib.fakefs import FakefsCacher

    cacher = megfile.smart_cache('/path/to/file')
    assert isinstance(cacher, NullCacher)
    with cacher as path:
        assert path == '/path/to/file'

    cacher = megfile.smart_cache('s3://path/to/file')
    assert isinstance(cacher, FakefsCacher)