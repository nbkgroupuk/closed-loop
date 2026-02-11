# frontend/js/card-input.js

// ===== CARD NUMBER: 4-4-4-4 FORMAT =====
const cardInput = document.getElementById("card_number");
cardInput.addEventListener("input", () => {
  let value = cardInput.value.replace(/\D/g, "").slice(0, 16);
  cardInput.value = value.replace(/(.{4})/g, "$1 ").trim();
});

// ===== EXPIRY DATE: MM/YY AUTO =====
const expiryInput = document.getElementById("expiry");
expiryInput.addEventListener("input", () => {
  let value = expiryInput.value.replace(/\D/g, "").slice(0, 4);

  if (value.length >= 3) {
    expiryInput.value = value.slice(0, 2) + "/" + value.slice(2);
  } else {
    expiryInput.value = value;
  }
});

// ===== CVV: NUMERIC ONLY =====
const cvvInput = document.getElementById("cvv");
cvvInput.addEventListener("input", () => {
  cvvInput.value = cvvInput.value.replace(/\D/g, "").slice(0, 4);
});

// ===== LUHN CHECK =====
function luhnCheck(num) {
  let sum = 0;
  let shouldDouble = false;

  for (let i = num.length - 1; i >= 0; i--) {
    let digit = parseInt(num[i], 10);
    if (shouldDouble) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
    shouldDouble = !shouldDouble;
  }
  return sum % 10 === 0;
}

// ===== EXPIRY VALIDATION =====
function expiryValid(mm, yy) {
  const now = new Date();
  const exp = new Date(`20${yy}`, mm);
  return exp > now;
}

// ===== ON SUBMIT VALIDATION =====
function validateCardForm() {
  const card = cardInput.value.replace(/\s/g, "");
  const expiry = expiryInput.value;
  const cvv = cvvInput.value;

  if (card.length !== 16 || !luhnCheck(card)) {
    alert("Invalid card number");
    return false;
  }

  if (!/^\d{2}\/\d{2}$/.test(expiry)) {
    alert("Invalid expiry format");
    return false;
  }

  const [mm, yy] = expiry.split("/");
  if (parseInt(mm) < 1 || parseInt(mm) > 12 || !expiryValid(mm, yy)) {
    alert("Card expired");
    return false;
  }

  if (cvv.length < 3) {
    alert("Invalid CVV");
    return false;
  }

  return true;
}
