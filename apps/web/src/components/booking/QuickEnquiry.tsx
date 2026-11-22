import EnquiryForm from './EnquiryForm';

/**
 * Homepage quick enquiry (lead-crm R3.1): name, phone, branch, optional date
 * and message. Saved as a `homepage_form` lead for the branch team to call back.
 */
export default function QuickEnquiry() {
  return (
    <EnquiryForm
      source="homepage_form"
      showDate
      messageLabel="What are you celebrating? (optional)"
      submitLabel="Request a call back"
    />
  );
}
