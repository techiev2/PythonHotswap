
import dis
from FuncModify import restart_func

def _find_traceframe(tb, code):
	while tb:
		if tb.tb_frame.f_code is code: return tb
		tb = tb.tb_next
	return None


def demo1():
	def demoFunc(a,b,c, raiseExc=None):
		print("a: %r" % a)
		while b > 0:
			print("b: %r" % b)
			if b == 4 and raiseExc: raise raiseExc
			if b == 2:
				b = 0
				continue
			b -= 1
		print("c: %r" % c)

	func = demoFunc
	try:
		# This prints:
		#   a: 'start'
		#   b: 5
		# And throws the exception then.
		demoFunc("start", 5, "end", Exception)
		assert False
	except Exception:
		print "! Exception"
		import sys
		_,_,tb = sys.exc_info()

	tb = _find_traceframe(tb, func.func_code)
	assert tb is not None

	# Start just one after the `raise`.
	instraddr = min([addr for (addr,_) in dis.findlinestarts(func.func_code) if addr > tb.tb_lasti])
	# Play around. Avoid that we throw the exception again.
	localdict = dict(tb.tb_frame.f_locals)
	localdict["b"] = 5
	localdict["raiseExc"] = None
	new_func = restart_func(func, instraddr=instraddr, localdict=localdict)

	# This prints:
	#   b: 4
	#   b: 3
	#   b: 2
	#   c: 'end'
	new_func()


def _calc_newlineno_via_diff(oldlineno, oldfilename, newfilename):
	from subprocess import Popen, PIPE
	diffcmd = ["diff", "-EbwB", "-U", "0"]
	diffout = Popen(diffcmd + [oldfilename, newfilename], stdout=PIPE).stdout.readlines()
	lineno = 1
	newlineno = 1
	import re
	r = re.compile(r"^@@ -([0-9]+).*@@.*$")
	for diffline in diffout:
		if lineno >= oldlineno:
			return newlineno
		if diffline.startswith("--- "): continue
		if diffline.startswith("+++ "): continue
		m = r.match(diffline)
		if m:
			nextlineno = int(m.groups()[0])
			if nextlineno > oldlineno:
				return newlineno + (oldlineno - lineno)
			newlineno += (nextlineno - lineno)
			lineno = nextlineno
			continue
		assert diffline[0:1] in "+-" # because of "diff -U 0"
		if diffline[0] == "+":
			newlineno += 1
		elif diffline[0] == "-":
			lineno += 1
	return newlineno

def demo2():
	# Let the user create some Python code.
	import os, tempfile
	editcmd = os.environ.get("EDITOR", "vi")
	tmpfn = tempfile.mktemp(suffix=".py")
	open(tmpfn, "w").write(
		"def main():\n"
		"	# Write some code here.\n"
		"	# When done, safe and exit. This code will get executed then.\n"
		"	# You can raise an exception via code here.\n"
		"	# Or just write an infinite loop and press Ctrl+C at execution.\n"
		"	import time\n"
		"	i = 0\n"
		"	while True:\n"
		"		i += 1\n"
		"		print i\n"
		"		time.sleep(1)\n"
		"\n"
	)
	os.system("%r %r" % (editcmd, tmpfn))

	# Make a backup of the file.
	tmpbackupfn = tempfile.mktemp(suffix=".py")
	os.system("cp %r %r" % (tmpfn, tmpbackupfn))

	# Now run the code.
	import imp
	tmpfnmod = imp.load_source("tmpfnmod", tmpfn)
	func = tmpfnmod.main
	try:
		func()
		assert False, "You must raise an exception for this demo."
	except BaseException:
		import sys
		excinfo = sys.exc_info()
		sys.excepthook(*excinfo)
		tb = excinfo[-1]
	tb = _find_traceframe(tb, func.func_code)
	assert tb is not None

	# Write hint about exception.
	lines = list(open(tmpfn).readlines())
	lineno = tb.tb_lineno - 1
	lines[lineno:lineno] = ["# The exception was raised in the line below!"]
	open(tmpfn, "w").writelines(lines)

	# Let the user edit the file again.
	os.system("%r %r" % (editcmd, tmpfn))

	# Reload file.
	tmpfnmod = imp.load_source("tmpfnmod", tmpfn)
	func = tmpfnmod.main
	# Calculate new line number.
	newlineno = _calc_newlineno_via_diff(tb.tb_lineno + 1, tmpbackupfn, tmpfn)
	print "Starting in line %i at %r" % (newlineno, open(tmpfn).readlines()[newlineno].strip("\n"))
	# Use that instruction address.
	instraddr = min([addr for (addr,lineno) in dis.findlinestarts(func.func_code) if lineno == newlineno])

	# Now, do the magic!
	# Create a modified function which jumps right to the previous place.
	newfunc = restart_func(func, instraddr=instraddr)
	# And run it.
	newfunc()


if __name__ == "__main__":
	import sys
	demoname = "demo1"
	if len(sys.argv) > 0: demoname = sys.argv[1]
	globals()[demoname]()
