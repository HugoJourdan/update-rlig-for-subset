# encoding: utf-8

###########################################################################################################
#
#
#	Filter without dialog plug-in
#
#	Read the docs:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/Filter%20without%20Dialog
#
#
###########################################################################################################

from __future__ import division, print_function, unicode_literals
import objc
import re
from GlyphsApp import *
from GlyphsApp.plugins import *

def get_auto_subsetted_axes(instance):
	font = instance.font
	if instance.customParameters["Disable Masters"]:
		disable_masters = instance.customParameters["Disable Masters"]

		axis_values = {i:set() for i, _ in enumerate(font.axes)}
		for master in font.masters:
			if master.name in disable_masters:
				pass
			else:
				for i, axis_value in enumerate(master.internalAxesValues):
					axis_values[i].add(axis_value)
		axes_kept = [axis.axisTag for i, axis in enumerate(font.axes) if len(axis_values[i]) != 1]

		return axes_kept
	else:
		return [axis.axisTag for axis in font.axes]


class UpdaterligForSubset(FilterWithoutDialog):
	
	@objc.python_method
	def settings(self):
		self.menuName = Glyphs.localize({
			"en": "Update rlig for subset",
			
			})

	@objc.python_method
	def filter(self, layer, inEditView, customParameters):
		

		


		axis_list = customParameters[0].split(',') if customParameters else "auto"

		font = layer.font()

		if layer.parent != font.glyphs[0]:
			return

		for instance in font.instances:
			if instance.type == 0:

				input_string = font.features["rlig"].code

				if instance.customParameters["Disable Masters"] and customParameters[0] == "auto":
					myTags = get_auto_subsetted_axes(instance)
				else:
					myTags = axis_list

				# Function to extract tags from a condition line, excluding the word "condition"
				def extract_tags(condition):
					return [tag for tag in re.findall(r'[a-zA-Z]+', condition) if tag != "condition"]

				# Function to check if all tags in the condition are in the allowed list
				def condition_has_allowed_tags(condition, allowed_tags):
					tags = extract_tags(condition)
					return all(tag in allowed_tags for tag in tags)

				# Split the input into lines
				lines = input_string.split('\n')

				current_block = []
				filtered_output = []
				inside_condition_block = False

				for line in lines:
					if line.startswith('condition'):
						if inside_condition_block:
							condition_line = current_block[0]
							if condition_has_allowed_tags(condition_line, myTags):
								filtered_output.extend(current_block)
							current_block = []
						inside_condition_block = True
						current_block.append(line)
					elif inside_condition_block:
						current_block.append(line)
						if line.strip() == "" or line.startswith('condition'):
							condition_line = current_block[0]
							if condition_has_allowed_tags(condition_line, myTags):
								filtered_output.extend(current_block)
							current_block = []
							inside_condition_block = False
							if line.startswith('condition'):
								inside_condition_block = True
								current_block.append(line)
					else:
						filtered_output.append(line)

				# Check for the last condition block
				if current_block:
					condition_line = current_block[0]
					if condition_has_allowed_tags(condition_line, myTags):
						filtered_output.extend(current_block)

				if not "#endif" in filtered_output:
					filtered_output.append("#endif")
				# Join the filtered output lines to form the final string
				filtered_string = '\n'.join(filtered_output)

				if font.features["rlig"].code != filtered_string:
					font.features["rlig"].code = filtered_string


	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
