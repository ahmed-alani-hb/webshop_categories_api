# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import cint, get_url

# Import from webshop module - these are internal functions we can use
from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder
from webshop.webshop.product_data_engine.query import ProductQuery
from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website, get_parent_item_groups


@frappe.whitelist(allow_guest=True)
def get_all_categories():
	"""
	Get all item categories with images and hierarchy
	
	Returns:
		dict: Categories data with image URLs and structure
	"""
	try:
		# Get settings to check which categories are enabled
		settings = frappe.get_cached_doc("Webshop Settings")
		base_url = get_url()
		
		# Always return item groups as primary categories
		categories = frappe.db.get_all(
			"Item Group",
			filters={"show_in_website": 1},
			fields=["name", "item_group_name", "parent_item_group", "is_group", "image", "route", "weightage", "description"],
			order_by="weightage DESC, name ASC"
		)
		
		# Process image URLs and add item counts
		for category in categories:
			if category.get('image'):
				category['image_url'] = base_url + category['image']
			else:
				category['image_url'] = None
				
			# Add item count
			category['item_count'] = frappe.db.count('Website Item', {
				'item_group': category['name'],
				'published': 1
			})
		
		result = {
			'status': 'success',
			'data': {
				'item_groups': categories
			},
			'count': len(categories),
			'settings': {
				'enable_field_filters': settings.enable_field_filters
			}
		}
		
		# Add other category types if field filters are enabled
		if settings.enable_field_filters:
			try:
				filter_categories = [row.fieldname for row in settings.filter_fields]
				
				# Remove item_group as we already have it
				other_categories = [cat for cat in filter_categories if cat != 'item_group']
				
			except Exception as e:
				frappe.log_error(f"Error loading other categories: {str(e)}")
		
		return result
		
	except Exception as e:
		frappe.log_error(f"Error in get_all_categories: {str(e)}")
		return {
			'status': 'error',
			'message': str(e)
		}


