python
import sys
sys.path.append("./gdb_chibios")
import coredump
end

break _screaming_death
commands
gcore
cont
end

break debug_threads
commands
gcore
cont
end

catch signal SIGSEGV
command
run
end

mon vect disable reset

