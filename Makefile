.PHONY: on off status run-brief help all chat brief

TARGET := $(word 2,$(MAKECMDGOALS))
SERVICE := $(if $(TARGET),$(TARGET),all)

on:
	@./svc on $(SERVICE)

off:
	@./svc off $(SERVICE)

status:
	@./svc status $(SERVICE)

run-brief:
	@./svc run-brief

help:
	@printf '%s\n' \
	  'make on [all|chat|brief]' \
	  'make off [all|chat|brief]' \
	  'make status [all|chat|brief]' \
	  'make run-brief'

all chat brief:
	@:
