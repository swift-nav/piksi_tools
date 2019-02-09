# Hack to make sure pip is always updated to the version specified
python -m pip install --upgrade pip==19.0.1 setuptools_scm

python -m pip install install $args
