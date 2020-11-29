#!/usr/bin/python

import glob
import os
import sys

from PIL import Image

"""By Wote
http://www.reddit.com/r/programming/comments/hql8b/looks_like_it_for_the_last_few_months_i_have_had/c1xkcdd
http://www.ruanyifeng.com/blog/2011/07/principle_of_similar_image_search.html

使用的时候，第一个参数是基准图片，第二个参数是用来比较的其他图片所在的目录，返回结果是两张图片之间不相同的数据位数量（汉明距离）。

这种算法的优点是简单快速，不受图片大小缩放的影响，缺点是图片的内容不能变更。如果在图片上加几个文字，它就认不出来了。所以，它的最佳用途是根据缩略图，找出原图。

实际应用中，往往采用更强大的pHash算法和SIFT算法，它们能够识别图片的变形。只要变形程度不超过25%，它们就能匹配原图。这些算法虽然更复杂，但是原理与上面的简便算法是一样的，就是先将图片转化成Hash字符串，然后再进行比较。

"""

EXTS = 'jpg', 'jpeg', 'JPG', 'JPEG', 'gif', 'GIF', 'png', 'PNG'

def avhash(im):
    if not isinstance(im, Image.Image):
        im = Image.open(im)
    im = im.resize((8, 8), Image.ANTIALIAS).convert('L')
    avg = reduce(lambda x, y: x + y, im.getdata()) / 64.
    return reduce(lambda x, (y, z): x | (z << y),
                  enumerate(map(lambda i: 0 if i < avg else 1, im.getdata())),
                  0)

def hamming(h1, h2):
    h, d = 0, h1 ^ h2
    while d:
        h += 1
        d &= d - 1
    return h

if __name__ == '__main__':
    if len(sys.argv) <= 1 or len(sys.argv) > 3:
        print "Usage: %s image.jpg [dir]" % sys.argv[0]
    else:
        im, wd = sys.argv[1], '.' if len(sys.argv) < 3 else sys.argv[2]
        h = avhash(im)

        os.chdir(wd)
        images = []
        for ext in EXTS:
            images.extend(glob.glob('*.%s' % ext))

        seq = []
        prog = int(len(images) > 50 and sys.stdout.isatty())
        for f in images:
            seq.append((f, hamming(avhash(f), h)))
            if prog:
                perc = 100. * prog / len(images)
                x = int(2 * perc / 5)
                print '\rCalculating... [' + '#' * x + ' ' * (40 - x) + ']',
                print '%.2f%%' % perc, '(%d/%d)' % (prog, len(images)),
                sys.stdout.flush()
                prog += 1

        if prog: print
        for f, ham in sorted(seq, key=lambda i: i[1]):
            print "%d\t%s" % (ham, f)

