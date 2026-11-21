import EnquiryForm from './EnquiryForm';

/**
 * Contact page form (lead-crm R3.4): branch, optional email, and a message.
 * Posts to POST /public/enquiries as a `contact_form` lead (the legacy
 * /public/contact endpoint stays for old clients).
 */
export default function ContactForm() {
  return (
    <EnquiryForm
      source="contact_form"
      showEmail
      messageLabel="Message (optional)"
      submitLabel="Send message"
    />
  );
}
