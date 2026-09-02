/**
 * CAUFA Login Page - Improved JavaScript
 * Handles password toggle, form validation, and interactions
 */

(function () {
  // Password Toggle Functionality
  const passwordToggleBtn = document.getElementById('passwordToggle');
  const passwordInput = document.getElementById('password');
  const passwordToggleIcon = document.getElementById('passwordToggleIcon');

  if (passwordToggleBtn && passwordInput) {
    passwordToggleBtn.addEventListener('click', function (e) {
      e.preventDefault();

      const isPassword = passwordInput.type === 'password';
      passwordInput.type = isPassword ? 'text' : 'password';

      // Update icon
      if (isPassword) {
        passwordToggleIcon.classList.remove('fa-eye');
        passwordToggleIcon.classList.add('fa-eye-slash');
        passwordToggleBtn.setAttribute('aria-label', 'Hide password');
      } else {
        passwordToggleIcon.classList.remove('fa-eye-slash');
        passwordToggleIcon.classList.add('fa-eye');
        passwordToggleBtn.setAttribute('aria-label', 'Show password');
      }
    });
  }

  // Form Validation & Error Handling
  const loginForm = document.getElementById('loginForm');

  if (loginForm) {
    loginForm.addEventListener('submit', function (e) {
      const username = document.getElementById('username').value.trim();
      const password = document.getElementById('password').value;
      const loginError = document.getElementById('loginError');

      // Clear previous error
      if (loginError) {
        loginError.style.display = 'none';
      }

      // Basic validation
      if (!username || !password) {
        e.preventDefault();
        if (loginError) {
          loginError.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> <span>Please enter both username and password.</span>';
          loginError.style.display = 'block';
          loginError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }
    });

    // Clear error on input focus
    const inputs = loginForm.querySelectorAll('input[type="text"], input[type="password"]');
    inputs.forEach(input => {
      input.addEventListener('focus', function () {
        const loginError = document.getElementById('loginError');
        if (loginError) {
          loginError.style.display = 'none';
        }
      });
    });
  }

  // OTP Input Formatting
  const otpInput = document.getElementById('otp');
  if (otpInput) {
    otpInput.addEventListener('input', function (e) {
      // Remove any non-numeric characters
      this.value = this.value.replace(/[^0-9]/g, '');

      // Limit to 6 digits
      if (this.value.length > 6) {
        this.value = this.value.slice(0, 6);
      }

      // Auto-submit if 6 digits entered
      if (this.value.length === 6) {
        // Optional: Auto-submit MFA form
        // document.getElementById('mfaForm').submit();
      }
    });

    // Prevent copy-paste of non-numeric
    otpInput.addEventListener('paste', function (e) {
      e.preventDefault();
      const pastedText = (e.clipboardData || window.clipboardData).getData('text');
      const numericOnly = pastedText.replace(/[^0-9]/g, '');
      this.value = numericOnly.slice(0, 6);
    });
  }

  // Smooth scroll to errors
  function scrollToElement(element) {
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // Add focus styles for accessibility
  const formInputs = document.querySelectorAll('.form-input');
  formInputs.forEach(input => {
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && this.id === 'username') {
        document.getElementById('password').focus();
      }
      if (e.key === 'Enter' && this.id === 'password') {
        loginForm?.submit();
      }
    });
  });

  // Prevent multiple form submissions
  if (loginForm) {
    let isSubmitting = false;

    loginForm.addEventListener('submit', function (e) {
      if (isSubmitting) {
        e.preventDefault();
        return;
      }
      isSubmitting = true;

      // Re-enable after 3 seconds in case of network error
      setTimeout(() => {
        isSubmitting = false;
      }, 3000);
    });
  }

  // Fade in animation on load
  window.addEventListener('load', function () {
    const container = document.querySelector('.login-container');
    if (container) {
      container.style.opacity = '1';
    }
  });

  // Detect caps lock
  const passwordInputElement = document.getElementById('password');
  if (passwordInputElement) {
    let capsLockWarning = document.createElement('div');
    capsLockWarning.id = 'capsLockWarning';
    capsLockWarning.style.cssText = `
      display: none;
      font-size: 12px;
      color: #f57c00;
      margin-top: 6px;
      padding: 6px 8px;
      background: #fff8f0;
      border-left: 2px solid #f57c00;
      border-radius: 4px;
    `;
    capsLockWarning.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Caps Lock is ON';

    passwordInputElement.parentElement.insertAdjacentElement('afterend', capsLockWarning);

    passwordInputElement.addEventListener('keydown', function (e) {
      const isCapsLockOn = e.getModifierState && e.getModifierState('CapsLock');
      if (isCapsLockOn) {
        capsLockWarning.style.display = 'block';
      } else {
        capsLockWarning.style.display = 'none';
      }
    });

    passwordInputElement.addEventListener('keyup', function (e) {
      const isCapsLockOn = e.getModifierState && e.getModifierState('CapsLock');
      if (isCapsLockOn) {
        capsLockWarning.style.display = 'block';
      } else {
        capsLockWarning.style.display = 'none';
      }
    });
  }

  // Console message
  console.log('%cCAUFA System Portal', 'font-size: 20px; font-weight: bold; color: #1b5e3f;');
  console.log('%cUniting faculty and administrators through collaboration, service, and excellence.', 'color: #666;');
})();
