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


def get_category_records_custom(categories):
	"""
	Simplified implementation using existing webshop functions
	Focus on item_group only since it's the main category type
	"""
	categorical_data = {}
	
	for category in categories:
		if category == "item_group":
			# Use direct database query for item groups - this is exactly what webshop does
			categorical_data["item_group"] = frappe.db.get_all(
				"Item Group",
				filters={"show_in_website": 1},
				fields=["name", "item_group_name", "parent_item_group", "is_group", "image", "route", "weightage"],
				order_by="weightage DESC, name ASC"
			)
		else:
			# For other category types, use basic approach
			try:
				website_item_meta = frappe.get_meta("Website Item", cached=True)
				if not website_item_meta.has_field(category):
					continue
					
				field = website_item_meta.get_field(category)
				
				if field.fieldtype == "Link" and field.options:
					doctype = field.options
					
					# Check if doctype has basic fields
					meta = frappe.get_meta(doctype, cached=True)
					fields = ["name"]
					
					if meta.get_field("image"):
						fields.append("image")
					
					# Check for show_in_website field
					filters = {}
					if meta.get_field("show_in_website"):
						filters["show_in_website"] = 1
					
					categorical_data[category] = frappe.db.get_all(
						doctype, 
						fields=fields, 
						filters=filters,
						limit=100  # Reasonable limit
					)
				else:
					categorical_data[category] = []
					
			except Exception as e:
				frappe.log_error(f"Error fetching {category}: {str(e)}")
				categorical_data[category] = []

	return categorical_data


@frappe.whitelist(allow_guest=True)
def get_product_filter_data_enhanced(query_args=None):
	"""
	Enhanced version of webshop's get_product_filter_data that includes enhanced category data with images
	This overrides the original webshop API method to provide better category support
	"""
	if isinstance(query_args, str):
		query_args = json.loads(query_args)

	query_args = frappe._dict(query_args or {})

	if query_args:
		search = query_args.get("search")
		field_filters = query_args.get("field_filters", {})
		attribute_filters = query_args.get("attribute_filters", {})
		start = cint(query_args.start) if query_args.get("start") else 0
		item_group = query_args.get("item_group")
		from_filters = query_args.get("from_filters")
	else:
		search, attribute_filters, item_group, from_filters = None, None, None, None
		field_filters = {}
		start = 0

	# if new filter is checked, reset start to show filtered items from page 1
	if from_filters:
		start = 0

	# Enhanced sub_categories with images
	sub_categories = []
	if item_group:
		sub_categories = get_child_groups_for_website(item_group, immediate=True)
		# Add image URLs and additional data to sub_categories
		base_url = get_url()
		for subcat in sub_categories:
			subcat_details = frappe.db.get_value(
				'Item Group', 
				subcat['name'], 
				['image', 'item_group_name', 'description', 'weightage'],
				as_dict=True
			)
			if subcat_details:
				subcat['item_group_name'] = subcat_details.get('item_group_name')
				subcat['description'] = subcat_details.get('description')
				subcat['weightage'] = subcat_details.get('weightage', 0)
				if subcat_details.get('image'):
					subcat['image_url'] = base_url + subcat_details['image']
				else:
					subcat['image_url'] = None
			else:
				subcat['image_url'] = None
				
			# Add item count for each subcategory
			subcat['item_count'] = frappe.db.count('Website Item', {
				'item_group': subcat['name'],
				'published': 1
			})

	engine = ProductQuery()

	try:
		result = engine.query(
			attribute_filters,
			field_filters,
			search_term=search,
			start=start,
			item_group=item_group,
		)
	except Exception:
		frappe.log_error("Product query with filter failed")
		return {"exc": "Something went wrong!"}

	# Enhanced items with full image URLs
	items = result.get("items", [])
	base_url = get_url()
	for item in items:
		if item.get('website_image'):
			item['image_url'] = base_url + item['website_image']
		else:
			item['image_url'] = None
			
		if item.get('thumbnail'):
			item['thumbnail_url'] = base_url + item['thumbnail']
		else:
			item['thumbnail_url'] = None

	# discount filter data
	filters = {}
	discounts = result["discounts"]

	if discounts:
		filter_engine = ProductFiltersBuilder()
		filters["discount_filters"] = filter_engine.get_discount_filters(discounts)

	# Enhanced response with category information
	response = {
		"items": items,
		"filters": filters,
		"settings": engine.settings,
		"sub_categories": sub_categories,
		"items_count": result["items_count"],
	}
	
	# Add current category details if item_group is specified
	if item_group:
		category_details = frappe.db.get_value(
			'Item Group',
			item_group,
			['name', 'item_group_name', 'image', 'description', 'route', 'weightage', 'parent_item_group'],
			as_dict=True
		)
		if category_details:
			if category_details.get('image'):
				category_details['image_url'] = base_url + category_details['image']
			else:
				category_details['image_url'] = None
			response['current_category'] = category_details
	
	return response


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
				
				if other_categories:
					categorical_data = get_category_records_custom(other_categories)
					
					# Process image URLs for other categories
					for category_type, items in categorical_data.items():
						for item in items:
							if item.get('image'):
								item['image_url'] = base_url + item['image']
							else:
								item['image_url'] = None
					
					result['data'].update(categorical_data)
					result['categories'] = filter_categories
			except Exception as e:
				frappe.log_error(f"Error loading other categories: {str(e)}")
		
		return result
		
	except Exception as e:
		frappe.log_error(f"Error in get_all_categories: {str(e)}")
		return {
			'status': 'error',
			'message': str(e)
		}


@frappe.whitelist(allow_guest=True)
def get_category_tree():
	"""
	Get hierarchical category tree using webshop's existing functions
	
	Returns:
		dict: Hierarchical category tree
	"""
	try:
		def build_tree_recursive(parent_group=None):
			"""Build category tree using webshop's get_child_groups_for_website function"""
			if parent_group:
				# Use webshop's function to get immediate children
				categories = get_child_groups_for_website(parent_group, immediate=True)
			else:
				# Get root categories (no parent)
				categories = frappe.db.get_all(
					'Item Group',
					filters={
						'show_in_website': 1,
						'parent_item_group': ['is', 'not set']
					},
					fields=['name', 'route'],
					order_by='name ASC'
				)
			
			base_url = get_url()
			tree = []
			
			for category in categories:
				# Get additional details for each category
				category_details = frappe.db.get_value(
					'Item Group',
					category['name'],
					['item_group_name', 'image', 'weightage', 'description'],
					as_dict=True
				)
				
				if category_details:
					category.update(category_details)
				
				# Add image URL
				if category.get('image'):
					category['image_url'] = base_url + category['image']
				else:
					category['image_url'] = None
				
				# Add item count using same logic as webshop
				category['item_count'] = frappe.db.count('Website Item', {
					'item_group': category['name'],
					'published': 1
				})
				
				# Get children recursively
				category['children'] = build_tree_recursive(category['name'])
				
				tree.append(category)
			
			return tree
		
		tree = build_tree_recursive()
		
		return {
			'status': 'success',
			'data': tree
		}
		
	except Exception as e:
		frappe.log_error(f"Error in get_category_tree: {str(e)}")
		return {
			'status': 'error',
			'message': str(e)
		}


@frappe.whitelist(allow_guest=True)
def get_category_details(category_name):
	"""
	Get detailed information about a specific category
	
	Args:
		category_name (str): Name of the category
		
	Returns:
		dict: Detailed category information with relationships
	"""
	try:
		if not category_name:
			frappe.throw(_("category_name parameter is required"))
		
		# Get category details
		category = frappe.db.get_value(
			'Item Group',
			category_name,
			['name', 'item_group_name', 'image', 'description', 'show_in_website', 
			 'route', 'weightage', 'parent_item_group', 'is_group', 'include_descendants'],
			as_dict=True
		)
		
		if not category:
			frappe.throw(_("Category not found"))
			
		if not category.get('show_in_website'):
			frappe.throw(_("Category not available on website"))
		
		base_url = get_url()
		
		# Add image URL
		if category.get('image'):
			category['image_url'] = base_url + category['image']
		else:
			category['image_url'] = None
		
		# Get item count (including descendants if enabled)
		if category.get('include_descendants'):
			# Get all descendant groups
			descendant_groups = get_child_groups_for_website(category_name, include_self=True)
			group_names = [g['name'] for g in descendant_groups]
			
			category['item_count'] = frappe.db.count('Website Item', {
				'item_group': ['in', group_names],
				'published': 1
			})
			category['direct_item_count'] = frappe.db.count('Website Item', {
				'item_group': category_name,
				'published': 1
			})
		else:
			category['item_count'] = frappe.db.count('Website Item', {
				'item_group': category_name,
				'published': 1
			})
		
		# Get parent chain
		parent_groups = get_parent_item_groups(category_name)
		
		# Get direct children
		child_groups = get_child_groups_for_website(category_name, immediate=True)
		
		# Add image URLs to child groups
		for child in child_groups:
			child_details = frappe.db.get_value(
				'Item Group', 
				child['name'], 
				['image', 'item_group_name', 'description', 'weightage'],
				as_dict=True
			)
			if child_details:
				if child_details.get('image'):
					child['image_url'] = base_url + child_details['image']
				else:
					child['image_url'] = None
				child['item_group_name'] = child_details.get('item_group_name')
				child['description'] = child_details.get('description')
				child['weightage'] = child_details.get('weightage', 0)
			else:
				child['image_url'] = None
			
			# Add item count for child
			child['item_count'] = frappe.db.count('Website Item', {
				'item_group': child['name'],
				'published': 1
			})
		
		# Get sibling categories (same parent)
		siblings = []
		if category.get('parent_item_group'):
			siblings = get_child_groups_for_website(category['parent_item_group'], immediate=True)
			# Remove self from siblings
			siblings = [s for s in siblings if s['name'] != category_name]
			
			# Add image URLs to siblings
			for sibling in siblings:
				sibling_details = frappe.db.get_value(
					'Item Group', 
					sibling['name'], 
					['image', 'item_group_name'],
					as_dict=True
				)
				if sibling_details and sibling_details.get('image'):
					sibling['image_url'] = base_url + sibling_details['image']
					sibling['item_group_name'] = sibling_details.get('item_group_name')
				else:
					sibling['image_url'] = None
		
		return {
			'status': 'success',
			'data': {
				'category': category,
				'parent_groups': parent_groups,
				'child_groups': child_groups,
				'sibling_groups': siblings
			}
		}
		
	except Exception as e:
		frappe.log_error(f"Error in get_category_details: {str(e)}")
		return {
			'status': 'error',
			'message': str(e)
		}


@frappe.whitelist(allow_guest=True)
def get_category_breadcrumbs(category_name):
	"""
	Get breadcrumb navigation for a category
	
	Args:
		category_name (str): Name of the category
		
	Returns:
		dict: Breadcrumb data
	"""
	try:
		if not category_name:
			frappe.throw(_("category_name parameter is required"))
		
		# Get parent chain using webshop function
		breadcrumbs = get_parent_item_groups(category_name, from_item=False)
		
		# Add current category
		current_category = frappe.db.get_value(
			'Item Group',
			category_name,
			['name', 'item_group_name', 'route'],
			as_dict=True
		)
		
		if current_category:
			breadcrumbs.append({
				'name': current_category['item_group_name'],
				'route': current_category['route']
			})
		
		return {
			'status': 'success',
			'data': breadcrumbs
		}
		
	except Exception as e:
		frappe.log_error(f"Error in get_category_breadcrumbs: {str(e)}")
		return {
			'status': 'error',
			'message': str(e)
		}


@frappe.whitelist(allow_guest=True)
def search_categories(query, limit=10):
	"""
	Search categories by name
	
	Args:
		query (str): Search query
		limit (int): Maximum results to return
		
	Returns:
		dict: Search results with images
	"""
	try:
		if not query:
			frappe.throw(_("query parameter is required"))
		
		search_term = f"%{query}%"
		categories = frappe.db.get_all(
			'Item Group',
			filters={
				'show_in_website': 1,
				'item_group_name': ['like', search_term]
			},
			fields=['name', 'item_group_name', 'image', 'route', 'description'],
			order_by='item_group_name ASC',
			limit=cint(limit)
		)
		
		base_url = get_url()
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
		
		return {
			'status': 'success',
			'data': categories,
			'count': len(categories)
		}
		
	except Exception as e:
		frappe.log_error(f"Error in search_categories: {str(e)}")
		return {
			'status': 'error',
			'message': str(e)
		}
