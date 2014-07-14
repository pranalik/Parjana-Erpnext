# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr, extract_email_id

from utilities.transaction_base import TransactionBase
#from __future__ import unicode_literals
#import webnotes

import pickle

import gflags
import httplib2
from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run

import gdata
import atom.data
import gdata.data
import gdata.contacts.client
import gdata.contacts.data
from gdata.auth import OAuthSignatureMethod, OAuthToken, OAuthInputParams
from webnotes.model.doc import Document
import gdata.gauth
import gdata.contacts.client

rqst_token = ''

class DocType(TransactionBase):
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist

	def on_communication(self, comm):
		if webnotes.conn.get_value("Profile", extract_email_id(comm.sender), "user_type")=="System User":
			status = "Replied"
		else:
			status = "Open"
			
		webnotes.conn.set(self.doc, 'status', status)

	def autoname(self):
		# concat first and last name
		self.doc.name = " ".join(filter(None, 
			[cstr(self.doc.fields.get(f)).strip() for f in ["first_name", "last_name"]]))
		
		# concat party name if reqd
		for fieldname in ("customer", "supplier", "sales_partner"):
			if self.doc.fields.get(fieldname):
				self.doc.name = self.doc.name + "-" + cstr(self.doc.fields.get(fieldname)).strip()
				break
		
	def validate(self):
		self.validate_primary_contact()

	# def on_update(self):
	# 	webnotes.errprint("In Update")
	# 	#page_token = None
	# 	#while True:
	# 		with open('client.pickle') as pickle_file:
	# 			client = pickle.load(pickle_file)

	# 		query = gdata.contacts.client.ContactsQuery(max_results=25, showdeleted='True', updated_min=None, updated_max=None)

	# # to rerieve contacts from google
	# 		feed = client.get_contacts(query=query)

	# 		for contact in feed.entry:
	# 			try:
	# 				webnotes.errprint(contact)
	# 				contact_id=contact.id.text
	# 				if contact.name:
	# 					webnotes.errprint("good")
	# 					first_name=contact.name.given_name
	# 					last_name=contact.name.family_name
	# 				for email in contact.email:
	# 					if email.primary and email.primary == 'true':
	# 						e=email.address
	# 						webnotes.errprint(e)
	# 				for phone_number in contact.phone_number:
	# 						num=phone_number.text
	# 						webnotes.errprint(num)	
	# 				d = Document("Contact")
	# 				d.contact_id=contact_id.text
	# 				d.first_name=first_name
	# 				d.last_name=last_name
	# 				d.phone=num
	# 				d.email_id=e
	# 				d.save()

	# 			#webnotes.errprint(contact.name.full_name)
	# 			#webnotes.errprint(contact.name.given_name)
	# 			#webnotes.errprint(contact.name.family_name)
	# 		# for email in contact.email:
	# 		# 	if email.primary and email.primary == 'true':
	# 		# 		webnotes.errprint( '    %s' % (email.address))
	# 		# for phone_number in contact.phone_number:
	# 		# 	#if email.primary and email.primary == 'true':
	# 		# 	webnotes.errprint( '    %s' % (phone_number.text))
	# 			except gdata.client.Unauthorized, err:
	# 				webnotes.errprint(err.message)


	def validate_primary_contact(self):
		sql = webnotes.conn.sql
		if self.doc.is_primary_contact == 1:
			if self.doc.customer:
				sql("update tabContact set is_primary_contact=0 where customer = '%s'" % (self.doc.customer))
			elif self.doc.supplier:
				sql("update tabContact set is_primary_contact=0 where supplier = '%s'" % (self.doc.supplier))	
			elif self.doc.sales_partner:
				sql("update tabContact set is_primary_contact=0 where sales_partner = '%s'" % (self.doc.sales_partner))
		else:
			if self.doc.customer:
				if not sql("select name from tabContact where is_primary_contact=1 and customer = '%s'" % (self.doc.customer)):
					self.doc.is_primary_contact = 1
			elif self.doc.supplier:
				if not sql("select name from tabContact where is_primary_contact=1 and supplier = '%s'" % (self.doc.supplier)):
					self.doc.is_primary_contact = 1
			elif self.doc.sales_partner:
				if not sql("select name from tabContact where is_primary_contact=1 and sales_partner = '%s'" % (self.doc.sales_partner)):
					self.doc.is_primary_contact = 1

	def on_trash(self):
		webnotes.conn.sql("""update `tabSupport Ticket` set contact='' where contact=%s""",
			self.doc.name)

@webnotes.whitelist()
def read_contact():
	with open('client.pickle') as pickle_file:
		client = pickle.load(pickle_file)

	query = gdata.contacts.client.ContactsQuery(max_results=25, showdeleted='True', updated_min=None, updated_max=None)

	# to rerieve contacts from google
	feed = client.get_contacts(query=query)
	lst=[]
	for contact in feed.entry:
		try:
			contact_id=contact.id.text
			if contact.name:
				
				first_name=contact.name.given_name.text
				last_name=contact.name.family_name.text
				
			for email in contact.email:
				if email.primary and email.primary == 'true':
					e=email.address
					#webnotes.errprint(e)
			for phone_number in contact.phone_number:
				num=phone_number.text
			#lst.append(first_name+' '+last_name+'  id --- '+contact_id)
			contactlist=webnotes.conn.sql("select name from `tabContact`", as_list=1)
			#webnotes.errprint(contactlist)
			
			fname=[]
			fupdate=[]
			if contact.name:
				fname.append(contact.name.full_name.text)
				#webnotes.errprint(fname)
				qry= webnotes.conn.sql("select modified from `tabContact` where name= %s ",(contact.name.full_name.text) , as_list=1)
				fupdate.append(contact.updated.text)
				if fname not in contactlist:
					webnotes.errprint("in document")
					d = Document("Contact")
					d.contact_id=contact_id
					d.first_name=first_name
					d.last_name=last_name
					d.phone=num
					d.email_id=e
					d.save()
					webnotes.errprint(d.name)
				elif fupdate > qry:
					webnotes.errprint("in contact update")
					r=webnotes.conn.sql("update `tabContact` set first_name=%s, last_name=%s, email_id=%s, phone=%s where name=%s",(contact.name.given_name.text,contact.name.family_name.text,e,num,contact.name.full_name.text))
					webnotes.errprint("contact Updated...")
		except gdata.client.Unauthorized, err:
			webnotes.errprint(err.message)
	#webnotes.errprint(lst)