#!/usr/bin/env bash
# Build AGEMA's dependencies in user space under ~/h2h/deps (no system changes).
set -euxo pipefail
D=$HOME/h2h/deps; mkdir -p $D; cd $D
[ -d boost_1_73_0 ] || { curl -sSL -o boost.tar.bz2 https://archives.boost.io/release/1.73.0/source/boost_1_73_0.tar.bz2 && tar xjf boost.tar.bz2 && rm boost.tar.bz2; }
[ -d abc ] || git clone -q --depth 1 https://github.com/berkeley-abc/abc.git
[ -f abc/libabc.so ] || (cd abc && make -j3 ABC_USE_PIC=1 libabc.so)
[ -d cudd ] || git clone -q --depth 1 https://github.com/ivmai/cudd.git
if [ ! -d cudd/lib/lib ]; then (cd cudd && (autoreconf -fi >/dev/null 2>&1 || true) && ./configure --enable-shared --prefix=$D/cudd/lib >/dev/null && make -j3 >/dev/null && make install >/dev/null); fi
[ -d sylvan ] || { git clone -q https://github.com/trolando/sylvan.git && (cd sylvan && git checkout -q 5e9da9782885f6215f6b509ac250212df30aaf70); }
if [ ! -f sylvan/build/src/libsylvan.so ]; then (cd sylvan && mkdir -p build && cd build && cmake .. -DBUILD_SHARED_LIBS=ON -DSYLVAN_BUILD_EXAMPLES=OFF -DSYLVAN_BUILD_DOCS=OFF >/dev/null && make -j3 >/dev/null); fi
echo AGEMA_DEPS_DONE
