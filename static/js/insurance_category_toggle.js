(function($) {
    'use strict';
    
    $(document).ready(function() {
        var sponsorshipField = $('#id_sponsorship');
        var insuranceCategoryRow = $('.field-insurance_category');
        
        function toggleInsuranceCategory() {
            var sponsorshipValue = sponsorshipField.val();
            if (sponsorshipValue && sponsorshipValue !== '') {
                insuranceCategoryRow.show();
            } else {
                insuranceCategoryRow.hide();
                // إلغاء اختيار فئة التأمين إذا لم تكن الكفالة محددة
                $('#id_insurance_category').val('');
            }
        }
        
        // تشغيل عند تحميل الصفحة
        toggleInsuranceCategory();
        
        // تشغيل عند تغيير الكفالة
        sponsorshipField.on('change', toggleInsuranceCategory);
    });
})(django.jQuery);
