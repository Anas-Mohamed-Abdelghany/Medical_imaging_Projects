using UnityEngine;
using System.Collections;

public class PuzzlePiece : MonoBehaviour
{
    public Transform[] targetPositions;  // Array of target positions for the puzzle pieces
    public float snapThreshold = 0.5f;   // The distance within which the puzzle piece will snap
    public float moveSpeed = 5f;         // Speed at which the puzzle piece will move
    public Light targetLight;            // The light to indicate proximity
    
    // Private fields
    private bool isSnapped = false;
    private int currentTargetIndex = 0;
    private Vector3 currentPosition;
    private bool isMoving = false;
    private Vector3 targetPosition;
    private Quaternion targetRotation;
    private bool isSelected = false;

    void Start()
    {
        // Initialize positions
        currentPosition = transform.position;
        targetPosition = transform.position;
        targetRotation = transform.rotation;

        // Ensure the light is initially turned off
        if (targetLight != null)
        {
            targetLight.enabled = false;
        }
    }

    void Update()
    {
        if (isSnapped) return;

        if (targetPositions != null && targetPositions.Length > 0 && currentTargetIndex < targetPositions.Length)
        {
            // Calculate distance to current target
            float distanceToTarget = Vector3.Distance(transform.position, targetPositions[currentTargetIndex].position);

            // Check if piece is close enough to snap
            if (distanceToTarget <= snapThreshold)
            {
                MoveToTargetSmoothly();
            }
            else if (isSelected && !isMoving)
            {
                HandleMovement();
            }

            // Update light based on proximity
            if (targetLight != null)
            {
                targetLight.enabled = distanceToTarget <= snapThreshold * 2f;
            }
        }

        // Handle movement to target position if moving
        if (isMoving)
        {
            float step = moveSpeed * Time.deltaTime;
            transform.position = Vector3.MoveTowards(transform.position, targetPosition, step);
            transform.rotation = Quaternion.RotateTowards(transform.rotation, targetRotation, step * 90f);

            if (Vector3.Distance(transform.position, targetPosition) < 0.001f)
            {
                isMoving = false;
            }
        }
    }

    void HandleMovement()
    {
        Vector3 movement = Vector3.zero;

        // WASD movement
        if (Input.GetKey(KeyCode.W)) movement.z += 1;
        if (Input.GetKey(KeyCode.S)) movement.z -= 1;
        if (Input.GetKey(KeyCode.A)) movement.x -= 1;
        if (Input.GetKey(KeyCode.D)) movement.x += 1;

        // Up/Down movement
        if (Input.GetKey(KeyCode.E)) movement.y += 1;
        if (Input.GetKey(KeyCode.Q)) movement.y -= 1;

        if (movement != Vector3.zero)
        {
            movement.Normalize();
            targetPosition = transform.position + movement * moveSpeed * Time.deltaTime;
            isMoving = true;
        }
    }

    void MoveToTargetSmoothly()
    {
        if (targetPositions == null || currentTargetIndex >= targetPositions.Length) return;

        Transform currentTarget = targetPositions[currentTargetIndex];
        
        // Set target position and rotation
        targetPosition = currentTarget.position;
        targetRotation = currentTarget.rotation;
        isMoving = true;

        // Check if very close to target
        if (Vector3.Distance(transform.position, targetPosition) <= 0.1f)
        {
            SnapToTarget();
        }
    }

    void SnapToTarget()
    {
        if (targetPositions == null || currentTargetIndex >= targetPositions.Length) return;

        // Snap to exact position and rotation
        transform.position = targetPositions[currentTargetIndex].position;
        transform.rotation = targetPositions[currentTargetIndex].rotation;

        // Update states
        isSnapped = true;
        isMoving = false;
        isSelected = false;

        // Handle physics
        Rigidbody rb = GetComponent<Rigidbody>();
        if (rb != null)
        {
            rb.isKinematic = true;
        }

        // Turn off light
        if (targetLight != null)
        {
            targetLight.enabled = false;
        }

        // Move to next target
        currentTargetIndex++;
        if (currentTargetIndex >= targetPositions.Length)
        {
            currentTargetIndex = 0;
        }
    }

    // Public methods for external control
    public void Select()
    {
        if (!isSnapped)
        {
            isSelected = true;
        }
    }

    public void Deselect()
    {
        isSelected = false;
    }

    public bool IsSnapped()
    {
        return isSnapped;
    }
}